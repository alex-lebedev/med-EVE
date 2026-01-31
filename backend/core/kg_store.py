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
        # Prioritize marker nodes and their incident edge endpoints so edges are not dropped
        marker_set = set(marker_ids) & set(self.nodes.keys())
        priority_1 = list(marker_set)
        edge_incident = set()
        for nid in marker_set:
            for edge in self.adj.get(nid, []):
                edge_incident.add(edge["from"])
                edge_incident.add(edge["to"])
        priority_2 = sorted(edge_incident - marker_set)
        all_2hop = set(marker_set) | edge_incident
        for marker in marker_set:
            neighbors = self.get_neighbors(marker, hops)
            all_2hop.update(neighbors)
        remainder = sorted(all_2hop - marker_set - edge_incident)
        ordered = priority_1 + priority_2 + remainder
        all_nodes = ordered[:max_nodes]
        subgraph_nodes = [self.nodes[nid] for nid in all_nodes if nid in self.nodes]
        subgraph_edges = [e for e in self.edges if e["from"] in all_nodes and e["to"] in all_nodes]
        return {"nodes": subgraph_nodes, "edges": subgraph_edges}

    def explain_edge(self, edge_id):
        for edge in self.edges:
            if edge['id'] == edge_id:
                return edge
        return None

# Global instance
kg_store = KGStore(os.path.join(os.path.dirname(__file__), '..', 'kg', 'graph.json'))