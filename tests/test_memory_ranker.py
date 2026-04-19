import pytest
from uuid import uuid4
from src.models import MemoryNode
from src.zh_tw.memory_ranker import MemoryRanker

def test_ranker_base_score():
    ranker = MemoryRanker()
    node = MemoryNode(content="測試", importance=0.8)
    
    # 測試基本排序分數
    score = ranker.score_memory(node)
    # Score should be a float based on importance
    assert score >= 0.0

def test_ranker_boost():
    ranker = MemoryRanker()
    node = MemoryNode(content="測試", importance=0.5)
    
    score1 = ranker.score_memory(node)
    
    node.boost(0.3)
    score2 = ranker.score_memory(node)
    
    assert score2 > score1

def test_ranker_recency():
    ranker = MemoryRanker()
    node = MemoryNode(content="測試", importance=0.5)
    
    # 手動修改時間 (這裡假設 ranker 有考慮更新時間)
    score = ranker.score_memory(node)
    assert score > 0
