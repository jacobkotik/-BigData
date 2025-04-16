import geopandas as gpd

gdf = gpd.read_file("..\data\ohio_counties.shp")
print(gdf.columns)
print(gdf.head())