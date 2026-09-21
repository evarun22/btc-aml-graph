"use client";

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { Graph } from "@/lib/types";

export default function GraphViewer({
  graph,
  height = 560,
}: {
  graph: Graph;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!graph.nodes.length) return;

    // Remove duplicate / invalid nodes
    const seenNodeIds = new Set<string>();
    const cleanNodes = graph.nodes.filter((node) => {
      if (!node.id || seenNodeIds.has(node.id)) {
        return false;
      }
      seenNodeIds.add(node.id);
      return true;
    });

    const nodeIds = new Set(cleanNodes.map((node) => node.id));

    // Remove edges that point to missing nodes
    const cleanEdges = graph.edges.filter((edge) => {
      const valid =
        edge.id &&
        edge.source &&
        edge.target &&
        nodeIds.has(edge.source) &&
        nodeIds.has(edge.target);

      if (!valid) {
        console.warn("Dropping invalid graph edge", edge);
      }

      return valid;
    });

    if (!cleanNodes.length) return;

    // IMPORTANT:
    // Cytoscape uses data.id as the element ID.
    // So we must make data.id match the node/edge ID we use for source/target.
    const nodeElements = cleanNodes.map((node) => {
      const data = { ...node.data };
      delete data.id;

      return {
        data: {
          id: node.id,
          ...data,
          label: data.label || node.id,
        },
      };
    });

    const edgeElements = cleanEdges.map((edge) => {
      const data = { ...edge.data };
      delete data.id;

      return {
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          ...data,
        },
      };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodeElements, ...edgeElements],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#334155",
            label: "data(label)",
            color: "#e2e8f0",
            "font-size": 10,
            "text-valign": "bottom",
            "text-halign": "center",
            width: 26,
            height: 26,
          },
        },
        {
          selector: 'node[data("is_sanctioned") = "true"]',
          style: {
            "background-color": "#7c3aed",
            "border-width": 3,
            "border-color": "#facc15",
          },
        },
        {
          selector: 'node[label = "Entity"]',
          style: {
            "background-color": "#0ea5e9",
            shape: "diamond",
          },
        },
        {
          selector: 'node[label = "Alert"]',
          style: {
            "background-color": "#f97316",
            shape: "triangle",
          },
        },
        {
          selector: 'node[label = "Tx"]',
          style: {
            "background-color": "#475569",
            shape: "round-rectangle",
          },
        },
        {
          selector: 'node[data("risk_level") = "CRITICAL"]',
          style: {
            "background-color": "#ef4444",
          },
        },
        {
          selector: 'node[data("risk_level") = "HIGH"]',
          style: {
            "background-color": "#f97316",
          },
        },
        {
          selector: 'node[data("risk_level") = "MEDIUM"]',
          style: {
            "background-color": "#f59e0b",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#475569",
            "target-arrow-color": "#475569",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 30,
      },
    });

    return () => cy.destroy();
  }, [graph]);

  if (!graph.nodes.length) {
    return (
      <div
        style={{ height }}
        className="flex w-full items-center justify-center rounded-xl border border-slate-800 bg-slate-950 text-sm text-slate-500"
      >
        No graph data available
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ height }}
      className="w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950"
    />
  );
}
