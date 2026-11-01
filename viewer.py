"""Plotly renders the exact triangulation used for STL export."""
import numpy as np
import plotly.graph_objects as go


def figure(mesh, show_dimensions=True, reset=0):
    v, f = mesh.vertices, mesh.faces
    fig = go.Figure(go.Mesh3d(
        x=v[:, 0].tolist(), y=v[:, 1].tolist(), z=v[:, 2].tolist(), i=f[:, 0].tolist(), j=f[:, 1].tolist(), k=f[:, 2].tolist(),
        color="#b8bcc0", flatshading=True,
        lighting=dict(ambient=.6, diffuse=.65, specular=0, roughness=1, fresnel=0,
                      facenormalsepsilon=0, vertexnormalsepsilon=0),
        lightposition=dict(x=200, y=-150, z=300),
        hoverinfo="skip", name="Solid",
    ))
    # Outline only real geometric edges; hide coplanar triangulation diagonals.
    adjacency = mesh.face_adjacency_edges[mesh.face_adjacency_angles > .4]
    if len(adjacency):
        points = np.full((len(adjacency), 3, 3), np.nan)
        points[:, :2, :] = v[adjacency]
        points = points.reshape(-1, 3)
        fig.add_trace(go.Scatter3d(x=points[:, 0], y=points[:, 1], z=points[:, 2],
                                  mode="lines", line=dict(color="#53585d", width=2),
                                  hoverinfo="skip", showlegend=False))
    x, y, z = mesh.extents
    span = max(x, y, z)
    offset = span*.11
    if show_dimensions:
        lines = [((0, y+offset, 0), (x, y+offset, 0), f"{x:g} mm"),
                 ((x+offset, 0, 0), (x+offset, y, 0), f"{y:g} mm"),
                 ((x+offset, y+offset, 0), (x+offset, y+offset, z), f"{z:g} mm")]
        for start, end, text in lines:
            mid = (np.array(start)+np.array(end))/2
            fig.add_trace(go.Scatter3d(x=[start[0], end[0]], y=[start[1], end[1]], z=[start[2], end[2]],
                                      mode="lines", line=dict(color="#999999", width=2), hoverinfo="skip", showlegend=False))
            fig.add_trace(go.Scatter3d(x=[mid[0]], y=[mid[1]], z=[mid[2]], mode="text", text=[text],
                                      textfont=dict(color="#555555", size=11), hoverinfo="skip", showlegend=False))
    axis = dict(showbackground=False, showgrid=False, zeroline=False, visible=False)
    fig.update_layout(
        height=540, margin=dict(l=0, r=0, t=5, b=5), paper_bgcolor="#F7F7F7",
        showlegend=False, uirevision=str(reset),
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, bgcolor="#F7F7F7", aspectmode="data",
                   camera=dict(eye=dict(x=1.55, y=1.7, z=1.1), up=dict(x=0, y=0, z=1)), dragmode="orbit"),
    )
    return fig
