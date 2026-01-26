import json
import os
from collections import defaultdict

class KGStore:
    def __init__(self, graph_file):
        with open(graph_file, 'r') as f:
            self.graph = json.load(f)
        self.nodes = {n['id']: n for n in self.graph['nodes']}
        self.edges = self.graph['edges']
        # Build adjacency list
        self.adj = defaultdict(list)
        for edge in self.edges:
            self.adj[edge['from']].append(edge)
            self.adj[edge['to']].append(edge)  # bidirectional for neighbors

    def get_neighbors(self, node_id, hops=1):
        visited = set()
        current = {node_id}
        for _ in range(hops):
            next_level = set()
            for n in current:
                if n not in visited:
                    visited.add(n)
                    for edge in self.adj[n]:
                        other = edge['to'] if edge['from'] == n else edge['from']
                        next_level.add(other)
            current = next_level
        return list(visited - {node_id})

    def subgraph_from_markers(self, marker_ids, hops=2, max_nodes=60):
        # Start from markers, get neighbors up to hops
        all_nodes = set(marker_ids)
        for marker in marker_ids:
            neighbors = self.get_neighbors(marker, hops)
            all_nodes.update(neighbors)
        all_nodes = sorted(list(all_nodes))[:max_nodes]  # limit, sorted for determinism
        subgraph_nodes = [self.nodes[nid] for nid in all_nodes if nid in self.nodes]
        subgraph_edges = [e for e in self.edges if e['from'] in all_nodes and e['to'] in all_nodes]
        return {"nodes": subgraph_nodes, "edges": subgraph_edges}

    def explain_edge(self, edge_id):
        for edge in self.edges:
            if edge['id'] == edge_id:
                return edge
        return None

# Global instance
kg_store = KGStore(os.path.join(os.path.dirname(__file__), '..', 'kg', 'graph.json'))