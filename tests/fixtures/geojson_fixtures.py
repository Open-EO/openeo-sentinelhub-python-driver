class GeoJSON_Fixtures:
    polygon = {
        "type": "Polygon",
        "coordinates": [[[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]]],
    }
    multi_polygon = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[102.0, 2.0], [103.0, 2.0], [103.0, 3.0], [102.0, 3.0], [102.0, 2.0]]],
            [
                [[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]],
                [[100.2, 0.2], [100.8, 0.2], [100.8, 0.8], [100.2, 0.8], [100.2, 0.2]],
            ],
        ],
    }
    point = {"type": "Point", "coordinates": [100.0, 0.0]}

    polygon_feature = {
        "type": "Feature",
        "geometry": polygon,
    }

    multi_polygon_feature = {
        "type": "Feature",
        "geometry": multi_polygon,
    }

    polygon_feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": polygon,
            },
            {"type": "Feature", "geometry": polygon},
        ],
    }

    polygon_multi_polygon_feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": polygon,
            },
            {"type": "Feature", "geometry": multi_polygon},
        ],
    }

    polygon_geometry_collection = {"type": "GeometryCollection", "geometries": [polygon, polygon]}

    polygon_multi_polygon_geometry_collection = {"type": "GeometryCollection", "geometries": [polygon, multi_polygon]}

    point_feature = {
        "type": "Feature",
        "geometry": point,
    }

    polygon_point_feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": polygon,
            },
            {"type": "Feature", "geometry": point},
        ],
    }

    polygon_point_geometry_collection = {"type": "GeometryCollection", "geometries": [polygon, point]}
