"""
Extend the static subgraph with synthetic nodes and edges for markers not in the KG.
Markers like ANC get a node and edges to existing patterns per dynamic_marker_edges.yml.
"""
import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "dynamic_marker_edges.yml")

_dynamic_edges_config = None


def _load_config():
    global _dynamic_edges_config
    if _dynamic_edges_config is None:
        if os.path.isfile(_CONFIG_PATH):
            with open(_CONFIG_PATH) as f:
                _dynamic_edges_config = yaml.safe_load(f) or {}
        else:
            _dynamic_edges_config = {}
    return _dynamic_edges_config


def extend_subgraph(case_card: dict, subgraph: dict) -> dict:
    """
    Add synthetic nodes for marker node ids not present in subgraph, and synthetic
    edges from config (dynamic_marker_edges.yml). Only adds edges whose pattern_id
    is in case_card["signals"] and exists in the subgraph. Returns the same subgraph
    dict with nodes and edges extended in place.
    """
    nodes = subgraph.get("nodes") or []
    edges = subgraph.get("edges") or []
    subgraph_node_ids = {n["id"] for n in nodes}
    abnormal_markers = case_card.get("abnormal_markers") or []
    abnormal_marker_node_ids = case_card.get("abnormal_marker_node_ids") or []
    signals = set(case_card.get("signals") or [])

    marker_to_label = dict(zip(abnormal_marker_node_ids, abnormal_markers))
    dynamic_ids = [nid for nid in abnormal_marker_node_ids if nid not in subgraph_node_ids]
    if not dynamic_ids:
        return subgraph

    config = _load_config()
    edge_counter = [0]

    def next_edge_id(marker_node_id: str, pattern_id: str) -> str:
        edge_counter[0] += 1
        safe_m = marker_node_id.replace("m_", "")
        safe_p = pattern_id.replace("p_", "")
        return f"e_dyn_{safe_m}_{safe_p}_{edge_counter[0]}"

    for node_id in dynamic_ids:
        label = marker_to_label.get(node_id, node_id)
        nodes.append({
            "id": node_id,
            "type": "Marker",
            "label": label,
            "description": "User-provided lab (not in knowledge graph).",
            "dynamic": True,
        })
        subgraph_node_ids.add(node_id)

        marker_name = label
        rules = config.get(marker_name) or config.get(node_id) or []
        for rule in rules:
            pattern_id = rule.get("pattern_id")
            if not pattern_id or pattern_id not in signals:
                continue
            if pattern_id not in subgraph_node_ids:
                continue
            relation = rule.get("relation") or "SUPPORTS"
            rationale = rule.get("rationale") or ""
            edge_id = next_edge_id(node_id, pattern_id)
            edges.append({
                "id": edge_id,
                "from": node_id,
                "to": pattern_id,
                "relation": relation,
                "rationale": rationale,
                "source_label": "dynamic",
            })

    subgraph["nodes"] = nodes
    subgraph["edges"] = edges
    return subgraph
