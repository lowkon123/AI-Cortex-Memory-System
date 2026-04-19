import pytest
from uuid import uuid4
from src.memory_graph import MemoryGraph, RelationType

def test_graph_add_and_connect():
    graph = MemoryGraph()
    id1 = uuid4()
    id2 = uuid4()
    
    graph.add_memory(id1, entities=["AI", "Memory"])
    graph.add_memory(id2, entities=["Memory", "Logic"])
    
    graph.connect(id1, id2, RelationType.SUPPORTS)
    
    neighbors = graph.get_neighbors(id1)
    assert len(neighbors) == 1
    assert neighbors[0][0] == id2
    assert neighbors[0][1] == RelationType.SUPPORTS

def test_jump_recall():
    graph = MemoryGraph()
    id1 = uuid4()
    id2 = uuid4()
    id3 = uuid4()
    
    graph.connect(id1, id2, RelationType.REMINDS)
    graph.connect(id2, id3, RelationType.REMINDS)
    
    results = graph.jump_recall(id1, max_hops=2)
    # Results should contain id2 and id3
    ids = [r[0] for r in results]
    assert id2 in ids
    assert id3 in ids

def test_find_related_by_entity():
    graph = MemoryGraph()
    id1 = uuid4()
    graph.add_memory(id1, entities=["測試實體"])
    
    results = graph.find_related("測試實體")
    assert id1 in results
