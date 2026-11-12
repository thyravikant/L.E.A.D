"""Small geometry helpers (no GIS dependency).

For parcel-sized polygons a local equirectangular projection around the
polygon centroid is accurate to well under 0.1% of area, which is enough for
ledger-vs-map reconciliation. Production should use PostGIS ST_Area on a
metric CRS (e.g. UTM 43N), as described in the report.
"""
import math

R_EARTH = 6_371_008.8  # metres


def project(lon: float, lat: float, lon0: float, lat0: float):
    x = math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * R_EARTH
    return x, y


def unproject(x: float, y: float, lon0: float, lat0: float):
    lon = lon0 + math.degrees(x / (R_EARTH * math.cos(math.radians(lat0))))
    lat = lat0 + math.degrees(y / R_EARTH)
    return lon, lat


def ring_area_m2(ring):
    """Area of a lon/lat ring (list of [lon, lat]) in square metres."""
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    lon0 = sum(p[0] for p in pts) / len(pts)
    lat0 = sum(p[1] for p in pts) / len(pts)
    xy = [project(p[0], p[1], lon0, lat0) for p in pts]
    s = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def polygon_area_m2(geometry):
    """Area of a GeoJSON Polygon (outer ring minus holes)."""
    rings = geometry["coordinates"]
    area = ring_area_m2(rings[0])
    for hole in rings[1:]:
        area -= ring_area_m2(hole)
    return area
