import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from shapely.ops import triangulate
from shapely.geometry import Polygon, MultiPolygon

def polygon_to_3d_top(geometry, z_top):
    """
    Triangulate a 2D polygon (or multipolygon) to create the top surface
    of the extruded shape at height z_top.
    Returns vertex lists and face indices for Plotly Mesh3d.
    """
    if isinstance(geometry, MultiPolygon):
        polys = list(geometry.geoms)
    else:
        polys = [geometry]

    top_x, top_y, top_z = [], [], []
    top_i, top_j, top_k = [], [], []
    vertex_offset = 0

    for poly in polys:
        triangles = triangulate(poly)
        for tri in triangles:
            coords = list(tri.exterior.coords)  # (usually 4 points; last repeats first)
            # take the first 3 unique coordinates
            x_coords = [c[0] for c in coords[:3]]
            y_coords = [c[1] for c in coords[:3]]
            z_coords = [z_top, z_top, z_top]

            top_x.extend(x_coords)
            top_y.extend(y_coords)
            top_z.extend(z_coords)

            top_i.append(vertex_offset + 0)
            top_j.append(vertex_offset + 1)
            top_k.append(vertex_offset + 2)
            vertex_offset += 3

    return {
        'x': top_x,
        'y': top_y,
        'z': top_z,
        'i': top_i,
        'j': top_j,
        'k': top_k
    }

def polygon_side_walls(geometry, z_top):
    """
    Create side walls for an extruded polygon. For each polygon's exterior boundary,
    build two triangles per edge to create a vertical wall connecting z=0 (the base)
    to z=z_top (the top). Returns vertex lists and face indices for Plotly Mesh3d.
    """
    wall_x, wall_y, wall_z = [], [], []
    wall_i, wall_j, wall_k = [], [], []
    vertex_offset = 0

    if isinstance(geometry, MultiPolygon):
        polys = list(geometry.geoms)
    else:
        polys = [geometry]

    for poly in polys:
        # Get the exterior boundary of the polygon
        boundary = list(poly.exterior.coords)
        # Remove duplicate closing vertex if present
        if len(boundary) > 1 and boundary[0] == boundary[-1]:
            boundary = boundary[:-1]
        n = len(boundary)
        for idx in range(n):
            # Current vertex and next vertex (wrap around)
            x1, y1 = boundary[idx]
            x2, y2 = boundary[(idx + 1) % n]
            # Create four vertices for the edge:
            # top1, top2 (at z=z_top) and bottom1, bottom2 (at z=0)
            top1 = (x1, y1, z_top)
            top2 = (x2, y2, z_top)
            bot1 = (x1, y1, 0)
            bot2 = (x2, y2, 0)
            # Append these vertices
            wall_x.extend([top1[0], top2[0], bot1[0], bot2[0]])
            wall_y.extend([top1[1], top2[1], bot1[1], bot2[1]])
            wall_z.extend([top1[2], top2[2], bot1[2], bot2[2]])
            # Create two triangles for this wall edge:
            # Triangle 1: top1, top2, bot1
            wall_i.append(vertex_offset + 0)
            wall_j.append(vertex_offset + 1)
            wall_k.append(vertex_offset + 2)
            # Triangle 2: top2, bot2, bot1
            wall_i.append(vertex_offset + 1)
            wall_j.append(vertex_offset + 3)
            wall_k.append(vertex_offset + 2)
            vertex_offset += 4

    return {
        'x': wall_x,
        'y': wall_y,
        'z': wall_z,
        'i': wall_i,
        'j': wall_j,
        'k': wall_k
    }

def main():
    # 1. Read the Ohio counties shapefile
    gdf = gpd.read_file('../data/ohio_counties.shp')
    
    # 2. Read CSV with median income data
    df_income = pd.read_csv('../data/ohio_income.csv')
    
    # 3. Merge GeoDataFrame with income data.
    #    Adjust left_on column if necessary (e.g. if your shapefile uses 'name', 'NAMELSAD', etc.)
    gdf = gdf.merge(df_income, left_on='name', right_on='county_name', how='left')
    
    # 4. (Optional) Reproject to a planar coordinate system for more accurate X/Y (e.g., EPSG:26917 is UTM Zone 17N)
    if gdf.crs is not None and gdf.crs.to_epsg() != 26917:
        try:
            gdf = gdf.to_crs(epsg=26917)
        except Exception as e:
            print("Reprojection failed:", e)
    
    # 5. Compute scale factors
    # Offset so that the lowest income is 0, then multiply by scale_factor.
    min_inc = gdf['median_income'].min()
    # Adjust scale_factor to exaggerate the extrusion (tweak as needed)
    scale_factor = 1 
    # This will map the income difference (median_income - min_inc) into a height value.
    
    fig = go.Figure()

    # 6. For each county, generate the top surface and side walls.
    for idx, row in gdf.iterrows():
        if pd.isnull(row['median_income']) or row['geometry'] is None:
            continue

        # Calculate scaled height so that the minimum income corresponds to 0.
        z_top = (row['median_income'] - min_inc) * scale_factor

        # Generate the top surface mesh (triangulated)
        top_mesh = polygon_to_3d_top(row['geometry'], z_top)
        # Generate side walls for full extrusion.
        wall_mesh = polygon_side_walls(row['geometry'], z_top)

        # Use a constant color for a solid appearance.
        solid_color = "royalblue"

        # Create top surface Mesh3d trace.
        top_trace = go.Mesh3d(
            x=top_mesh['x'],
            y=top_mesh['y'],
            z=top_mesh['z'],
            i=top_mesh['i'],
            j=top_mesh['j'],
            k=top_mesh['k'],
            color=solid_color,
            flatshading=True,
            name=row['name'],
            hovertemplate=(
                f"<b>{row['name']}</b><br>"
                f"Median Income: ${row['median_income']}<br>"
                f"Height: {z_top:.2f}<extra></extra>"
            ),
            showscale=False
        )
        fig.add_trace(top_trace)
        
        # Create side walls Mesh3d trace.
        wall_trace = go.Mesh3d(
            x=wall_mesh['x'],
            y=wall_mesh['y'],
            z=wall_mesh['z'],
            i=wall_mesh['i'],
            j=wall_mesh['j'],
            k=wall_mesh['k'],
            color=solid_color,
            flatshading=True,
            name=row['name'] + " walls",
            hoverinfo='skip',  # Avoid duplicate hover info for walls.
            showscale=False
        )
        fig.add_trace(wall_trace)

    # 7. Configure layout with proper aspect ratio.
    fig.update_layout(
        title='Ohio Counties Extruded by Median Income',
        scene=dict(
            xaxis_title='X (m)',
            yaxis_title='Y (m)',
            zaxis_title='Extruded Income Height',
            aspectmode='data'
        )
    )
    fig.show()

if __name__ == '__main__':
    main()
