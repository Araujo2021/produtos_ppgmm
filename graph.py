from collections import Counter
import networkx as nx
import plotly.graph_objects as go

def coauthorship_edges(works):
    counter = Counter()
    for w in works:
        ds = sorted(set(d for d in w.get("docentes", []) if d != "Desconhecido"))
        for i in range(len(ds)):
            for j in range(i+1, len(ds)):
                counter[(ds[i], ds[j])] += 1
    return counter

def make_graph_figure(works, *args, **kwargs):
    min_year = kwargs.get("min_year") or (args[0] if args else None)
    edges = coauthorship_edges(works)
    G = nx.Graph()
    for (a,b), n in edges.items():
        G.add_edge(a,b,weight=n)
    if not G.nodes:
        return go.Figure(), edges

    pos = nx.spring_layout(G, seed=17, weight="weight", k=1.2)

    edge_traces = []
    annotations = []
    for a,b,data in G.edges(data=True):
        x0,y0 = pos[a]; x1,y1 = pos[b]
        n = data["weight"]
        edge_traces.append(go.Scatter(
            x=[x0,x1,None], y=[y0,y1,None],
            mode="lines",
            line=dict(width=max(1, min(8, 1+n*0.8))),
            hoverinfo="text",
            text=[f"{a} ↔ {b}: {n} artigo(s)"]*3,
            showlegend=False
        ))
        annotations.append(dict(
            x=(x0+x1)/2, y=(y0+y1)/2,
            text=str(n), showarrow=False,
            font=dict(size=15, color="#d32f2f", weight="bold"),
            yshift=-15,
            bgcolor="rgba(255,255,255,0.7)",
            borderpad=1
        ))

    degrees = dict(G.degree(weight="weight"))
    node_trace = go.Scatter(
        x=[pos[n][0] for n in G.nodes],
        y=[pos[n][1] for n in G.nodes],
        mode="markers+text",
        text=[n.title() for n in G.nodes],
        textposition="top center",
        hovertext=[f"{n.title()}<br>Colaborações ponderadas: {degrees[n]}" for n in G.nodes],
        hoverinfo="text",
        marker=dict(
            size=[18+min(24,degrees[n]*2) for n in G.nodes], 
            line=dict(width=2, color="white"),
            color=[degrees[n] for n in G.nodes],
            colorscale="Viridis",
            opacity=0.9,
            showscale=False
        ),
        showlegend=False
    )

    fig = go.Figure(data=edge_traces+[node_trace])
    title_text = f"Rede de colaboração entre docentes (a partir de {min_year})" if min_year else "Rede de colaboração entre docentes"
    fig.update_layout(
        title=title_text,
        hovermode="closest",
        margin=dict(l=10,r=10,t=50,b=10),
        annotations=annotations,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=720
    )
    return fig, edges
