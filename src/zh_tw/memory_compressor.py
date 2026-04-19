"""LLM 驅動的分層總結，用於記憶壓縮。

此模組處理 L0 和 L1 摘要的生成，
支援不同縮放級別的高效記憶檢索。
"""

from typing import Optional


class MemoryCompressor:
    """記憶壓縮的分層總結。

    生成多級摘要以支援基於縮放的檢索。
    需要外部 LLM API 進行實際總結。
    """

    def __init__(self, llm_client: Optional[object] = None):
        """使用可選的 LLM 客戶端初始化壓縮器。

        Args:
            llm_client: 用於總結的外部 LLM API 客戶端。
        """
        self.llm_client = llm_client

    async def compress_to_l1(self, content: str) -> str:
        """將內容壓縮至 L1 摘要（關鍵點）。

        Args:
            content: 完整的記憶內容。

        Returns:
            捕捉關鍵點的 L1 摘要。
        """
        if not self.llm_client:
            return self._fallback_l1(content)
        return await self._llm_summarize(content, max_tokens=500)

    async def compress_to_l0(self, content: str) -> str:
        """將內容壓縮至 L0 摘要（廣泛概述）。

        Args:
            content: 完整內容或 L1 摘要。

        Returns:
            提供廣泛概述的 L0 摘要。
        """
        if not self.llm_client:
            return self._fallback_l0(content)
        return await self._llm_summarize(content, max_tokens=100)

    def compress_batch(self, contents: list[str]) -> list[tuple[str, str]]:
        """將一批記憶壓縮至 L0 和 L1。

        Args:
            contents: 記憶內容列表。

        Returns:
            (l0_summary, l1_summary) 元組列表。
        """
        results = []
        for content in contents:
            l1 = self._fallback_l1(content) if not self.llm_client else None
            l0 = self._fallback_l0(content) if not self.llm_client else None
            results.append((l0 or "", l1 or ""))
        return results

    async def _llm_summarize(self, content: str, max_tokens: int) -> str:
        """調用外部 LLM 進行總結。

        Args:
            content: 要總結的內容。
            max_tokens: 摘要中的最大 tokens 數。

        Returns:
            生成摘要文本。
        """
        if not self.llm_client:
            raise RuntimeError("No LLM client configured")

        response = await self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"Summarize the following text in no more than {max_tokens} tokens. Focus on the most important points.",
                },
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _fallback_l1(self, content: str) -> str:
        """無 LLM 的簡單回退 L1 總結。

        Args:
            content: 完整內容。

        Returns:
            前 500 個字符加省略號。
        """
        if len(content) <= 500:
            return content
        return content[:500] + "..."

    def _fallback_l0(self, content: str) -> str:
        """無 LLM 的簡單回退 L0 總結。

        Args:
            content: 完整內容。

        Returns:
            前 100 個字符加省略號。
        """
        if len(content) <= 100:
            return content
        return content[:100] + "..."
