from shapely.geometry import Point, Polygon
import numpy as np
from collections import deque

def create_grid(polygon, resolution_km=10):
    shapely_polygon = Polygon(polygon)
    minx, miny, maxx, maxy = shapely_polygon.bounds

    grid_lines = []
    step = resolution_km/111

    x_step = step
    y_step = step

    steps_x = int((maxx-minx)/step)
    steps_y = int((maxy-miny)/step)

    start_x = minx
    start_y = miny

    for i in range(steps_x):
        for j in range(steps_y):
            cell_x = start_x + (i * x_step)
            cell_y = start_y + (j * y_step)

            center_x = cell_x + x_step/2
            center_y = cell_y + y_step/2

            coords1 = [cell_x, cell_y]
            coords2 = [cell_x+x_step, cell_y]
            coords3 = [cell_x+x_step, cell_y+y_step]
            coords4 = [cell_x, cell_y+y_step]

            point = Point(center_x, center_y)
            if shapely_polygon.contains(point):
                cell = [coords1, coords2, coords3, coords4]
                grid_lines.append({
                    "i": i,
                    "j": j,
                    "center_lat": center_y,
                    "center_lon": center_x,
                    "bounds": [coords1, coords2, coords3, coords4]
                })


    return grid_lines


def calculate_hotspots(grid_cells, risk_threshold=None, min_size=2):
    if not grid_cells:
        return []
        
    all_risks = [c.get("risk", 0) for c in grid_cells]
    
    if risk_threshold is None:
        risk_threshold = np.percentile(all_risks, 65) if all_risks else 0
        
    high_risk = [c for c in grid_cells if c.get("risk", 0) >= risk_threshold]
    high_risk_dict = {(c["i"], c["j"]): c for c in high_risk if "i" in c and "j" in c}
    
    visited = set()
    hotspots_centers = []
    
    for cell in high_risk:
        i, j = cell.get("i"), cell.get("j")
        if i is None or j is None or (i, j) in visited:
            continue
            
        group = []
        queue = deque()
        queue.append((i, j))
        
        while queue:
            ci, cj = queue.popleft()
            if (ci, cj) in visited:
                continue
                
            visited.add((ci, cj))
            group.append(high_risk_dict[(ci, cj)])
            
            for ni, nj in [(ci+1, cj), (ci-1, cj), (ci, cj+1), (ci, cj-1)]:
                if (ni, nj) in high_risk_dict and (ni, nj) not in visited:
                    queue.append((ni, nj))
                    
        if len(group) >= min_size:
            avg_lat = sum(c["lat"] for c in group) / len(group)
            avg_lon = sum(c["lon"] for c in group) / len(group)
            max_risk_in_group = max(c["risk"] for c in group)
            
            commercial_percentage = round(max_risk_in_group, 1)
            
            hotspots_centers.append({
                "lat": round(avg_lat, 4),
                "lon": round(avg_lon, 4),
                "cells_count": len(group),
                "max_risk": commercial_percentage 
            })
            
    return sorted(hotspots_centers, key=lambda x: x['max_risk'], reverse=True)