"""
Preprocessing scripts.

Written by Ed Oughton.

Winter 2020

"""
import os
import configparser
import json
import csv
import pandas as pd
import geopandas as gpd
import pyproj
from shapely.geometry import Polygon, MultiPolygon, mapping, shape, MultiLineString, LineString, box
from shapely.ops import transform, unary_union, nearest_points
import fiona
import fiona.crs
import rasterio
from rasterio.mask import mask
from rasterstats import zonal_stats
import networkx as nx
from rtree import index
import numpy as np
import random
import math

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW = os.path.join(BASE_PATH, 'raw')
DATA_INTERMEDIATE = os.path.join(BASE_PATH, 'intermediate')


def process_country_shape(iso3):
    """
    Creates a single national boundary for the desired country.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    print('----')

    path = os.path.join(DATA_INTERMEDIATE, iso3)

    if os.path.exists(os.path.join(path, 'tc_outline.shp')):
        return 'Completed national outline processing'

    if not os.path.exists(path):
        print('Creating directory {}'.format(path))
        os.makedirs(path)
    shape_path = os.path.join(path, 'tc_outline.shp')

    print('Loading all country shapes')
    path = os.path.join(DATA_RAW, 'gadm36_levels_shp', 'gadm36_0.shp')
    countries = gpd.read_file(path)

    print('Getting specific country shape for {}'.format(iso3))
    single_country = countries[countries.GID_0 == iso3]

    print('Excluding small shapes')
    single_country['geometry'] = single_country.apply(
        exclude_small_shapes, axis=1)

    print('Adding ISO country code and other global information')
    glob_info_path = os.path.join(BASE_PATH, 'global_information.csv')
    load_glob_info = pd.read_csv(glob_info_path, encoding = "ISO-8859-1")
    single_country = single_country.merge(
        load_glob_info,left_on='GID_0', right_on='ISO_3digit')

    print('Exporting processed country shape')
    single_country.to_file(shape_path, driver='ESRI Shapefile')

    return print('Processing country shape complete')


def process_regions(telecom_circle):
    """
    Function for processing the lowest desired subnational regions for the
    chosen telecom circle.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    regions = []

    tc_code = telecom_circle['tc_code']
    iso3 = telecom_circle['iso3']

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)

    if not os.path.exists(path):
        print('Creating directory {}'.format(path))
        os.makedirs(path)

    regional_levels = [2, 3]

    for regional_level in regional_levels:

        filename = 'regions_{}_{}.shp'.format(regional_level, tc_code)
        folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
        path_processed = os.path.join(folder, filename)

        if os.path.exists(path_processed):
            return

        path_lut = os.path.join(DATA_RAW, 'tc_lut_GID_2.csv')
        lut = pd.read_csv(path_lut)
        lut = lut[lut['tc_code'] == tc_code]
        lut = lut['GID_2'].tolist()

        print('----')
        print('Working on {} level {}'.format(tc_code, regional_level))

        if not os.path.exists(folder):
            os.mkdir(folder)

        filename = 'gadm36_{}.shp'.format(regional_level)
        path_regions = os.path.join(DATA_RAW, 'gadm36_levels_shp', filename)
        regions = gpd.read_file(path_regions, crs='epsg:4326')

        print('Subsetting {} level {}'.format(tc_code, regional_level))
        regions = regions[regions['GID_2'].isin(lut)]

        print('Excluding small shapes')
        regions['geometry'] = regions.apply(exclude_small_shapes, axis=1)

        try:
            print('Writing global_regions.shp to file')
            regions.to_file(path_processed, driver='ESRI Shapefile')
        except:
            print('Unable to write {}'.format(filename))

        tc_outline = regions.unary_union

        if tc_outline.geom_type == 'MultiPolygon':
            tc_outline = gpd.GeoDataFrame(
                {'geometry': tc_outline},
                crs='epsg:4326'
            )

        else:
            tc_outline = gpd.GeoDataFrame(
                {'geometry': tc_outline},
                crs='epsg:4326',
                index=[0]
            )

        path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'tc_outline.shp')
        tc_outline.to_file(path)

        print('Completed processing of regional shapes level {}'.format(regional_level))

    return print('complete')


def process_settlement_layer(telecom_circle):
    """
    Clip the settlement layer to the chosen telecom circle boundary and place in
    desired folder.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    regional_level = telecom_circle['regional_level']

    path_settlements = os.path.join(DATA_RAW,'settlement_layer',
        'ppp_2020_1km_Aggregated.tif')

    settlements = rasterio.open(path_settlements, 'r+')
    settlements.nodata = 255
    settlements.crs = {"epsg:4326"}

    path_tc_outline = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'tc_outline.shp')

    if os.path.exists(path_tc_outline):
        tc_outline = gpd.read_file(path_tc_outline)
    else:
        print('Must generate tc_outline.shp first' )

    path_tc = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)
    shape_path = os.path.join(path_tc, 'settlements.tif')

    if os.path.exists(shape_path):
        return print('Completed settlement layer processing')

    print('----')
    print('Working on {} level {}'.format(iso3, regional_level))

    bbox = box(
        tc_outline.total_bounds[0],
        tc_outline.total_bounds[1],
        tc_outline.total_bounds[2],
        tc_outline.total_bounds[3],
    )

    geo = gpd.GeoDataFrame()

    geo = gpd.GeoDataFrame({'geometry': bbox}, index=[0])

    coords = [json.loads(geo.to_json())['features'][0]['geometry']]

    #chop on coords
    out_img, out_transform = mask(settlements, coords, crop=True)

    # Copy the metadata
    out_meta = settlements.meta.copy()

    out_meta.update({"driver": "GTiff",
                    "height": out_img.shape[1],
                    "width": out_img.shape[2],
                    "transform": out_transform,
                    "crs": 'epsg:4326'})

    with rasterio.open(shape_path, "w", **out_meta) as dest:
            dest.write(out_img)

    return print('Completed processing of settlement layer')


def process_night_lights(telecom_circle):
    """
    Clip the nightlights layer to the chosen telecom circle boundary and
    place in desired country folder.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)
    path_output = os.path.join(folder,'night_lights.tif')

    if os.path.exists(path_output):
        return print('Completed processing of nightlight layer')

    path_tc_outline = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'tc_outline.shp')

    filename = 'F182013.v4c_web.stable_lights.avg_vis.tif'
    path_night_lights = os.path.join(DATA_RAW, 'nightlights', '2013',
        filename)

    tc_outline = gpd.read_file(path_tc_outline)

    print('----')
    print('working on {}'.format(iso3))

    bbox = box(
        tc_outline.total_bounds[0],
        tc_outline.total_bounds[1],
        tc_outline.total_bounds[2],
        tc_outline.total_bounds[3],
    )

    geo = gpd.GeoDataFrame()

    geo = gpd.GeoDataFrame({'geometry': bbox}, index=[0], crs=fiona.crs.from_epsg('4326'))

    coords = [json.loads(geo.to_json())['features'][0]['geometry']]

    night_lights = rasterio.open(path_night_lights, "r+")
    night_lights.nodata = 0

    out_img, out_transform = mask(night_lights, coords, crop=True)

    out_meta = night_lights.meta.copy()

    out_meta.update({"driver": "GTiff",
                    "height": out_img.shape[1],
                    "width": out_img.shape[2],
                    "transform": out_transform,
                    "crs": 'epsg:4326'})

    with rasterio.open(path_output, "w", **out_meta) as dest:
            dest.write(out_img)

    return print('Completed processing of night lights layer')


def process_coverage_shapes(telecom_circle):
    """
    Load in coverage maps, process and export for each telecom circle.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    level = telecom_circle['regional_level']
    iso3 = telecom_circle['iso3']
    iso2 = telecom_circle['iso2']
    tc_code = telecom_circle['tc_code']

    technologies = [
        'GSM',
        '3G',
        '4G'
    ]

    for tech in technologies:

        folder_coverage = os.path.join(DATA_INTERMEDIATE, iso3, 'national_coverage')
        filename = 'coverage_{}.shp'.format(tech)
        path_output = os.path.join(folder_coverage, filename)

        print('Working on {} in {}'.format(tech, tc_code))

        if not os.path.exists(path_output):

            filename = 'Inclusions_201812_{}.shp'.format(tech)
            folder = os.path.join(DATA_RAW, 'mobile_coverage_explorer_2019', 'Data_MCE')
            inclusions = gpd.read_file(os.path.join(folder, filename))

            if iso2 in inclusions['CNTRY_ISO2']:

                filename = 'MCE_201812_{}.shp'.format(tech)
                folder = os.path.join(DATA_RAW, 'mobile_coverage_explorer_2019', 'Data_MCE')
                coverage = gpd.read_file(os.path.join(folder, filename))

                coverage = coverage.loc[coverage['CNTRY_ISO3'] == iso3]

                print('Simplifying geometries')
                coverage['geometry'] = coverage.simplify(
                    tolerance = 1000,
                    preserve_topology=True).buffer(0.0001).simplify(
                    tolerance = 1000,
                    preserve_topology=True
                )

            else:

                filename = 'OCI_201812_{}.shp'.format(tech)
                folder = os.path.join(DATA_RAW, 'mobile_coverage_explorer_2019',
                    'Data_OCI')
                coverage = gpd.read_file(os.path.join(folder, filename))

                coverage = coverage.loc[coverage['CNTRY_ISO3'] == iso3]

                if len(coverage) > 0:

                    print('Dissolving polygons')
                    coverage['dissolve'] = 1
                    coverage = coverage.dissolve(by='dissolve', aggfunc='sum')
                    coverage = coverage.to_crs('epsg:3857')

                    print('Excluding small shapes')
                    coverage['geometry'] = coverage.apply(clean_coverage,axis=1)

                    print('Removing empty and null geometries')
                    coverage = coverage[~(coverage['geometry'].is_empty)]
                    coverage = coverage[coverage['geometry'].notnull()]

                    print('Simplifying geometries')
                    coverage['geometry'] = coverage.simplify(
                        tolerance = 1000,
                        preserve_topology=False).buffer(0.001).simplify(
                        tolerance = 1000,
                        preserve_topology=False
                    )

                    coverage = coverage.to_crs('epsg:4326')

                    if not os.path.exists(folder_coverage):
                        os.makedirs(folder_coverage)

                    coverage.to_file(path_output, driver='ESRI Shapefile')
        else:
            print('Preloading existing coverage shapes')
            coverage = gpd.read_file(path_output, crs='epsg:4326')

        folder_tc_coverage = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'coverage')
        filename = 'coverage_{}.shp'.format(tech)
        path_output = os.path.join(folder_tc_coverage, filename)

        if not os.path.exists(folder_tc_coverage):
            os.makedirs(folder_tc_coverage)

        if not os.path.exists(path_output):

            path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'tc_outline.shp')
            tc_outline = gpd.read_file(path)

            coverage = coverage[['geometry']]

            print('Overlaying tc_outline and coverage')
            coverage = gpd.overlay(coverage, tc_outline, how='intersection')

            filename = 'regions_{}_{}.shp'.format(level, tc_code)
            folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
            path = os.path.join(folder, filename)
            regions = gpd.read_file(path)

            print('Overlaying regions and coverage')
            coverage = gpd.overlay(coverage, regions, how='intersection')

            coverage.to_file(path_output, driver='ESRI Shapefile')

    print('Processed coverage shapes')


def process_regional_coverage(telecom_circle):
    """
    This functions estimates the area covered by each cellular
    technology.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    Returns
    -------
    output : dict
        Results for cellular coverage by each technology for
        each region.

    """
    level = telecom_circle['regional_level']
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    gid_level = 'GID_{}'.format(level)

    filename = 'regions_{}_{}.shp'.format(level, tc_code)
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
    path = os.path.join(folder, filename)
    regions = gpd.read_file(path)

    technologies = [
        'GSM',
        '3G',
        '4G'
    ]

    output = {}

    for tech in technologies:

        folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'coverage')
        path =  os.path.join(folder, 'coverage_{}.shp'.format(tech))

        if os.path.exists(path):

            coverage = gpd.read_file(path)

            coverage = coverage[['geometry']]

            coverage = gpd.overlay(regions, coverage, how='intersection')

            tech_coverage = {}

            for idx, region in coverage.iterrows():

                area_km2 = round(area_of_polygon(region['geometry']) / 1e6)

                tech_coverage[region[gid_level]] = area_km2

            output[tech] = tech_coverage

    return output


def get_regional_data(telecom_circle):
    """
    Extract regional data including luminosity and population.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    iso3 = telecom_circle['iso3']
    level = telecom_circle['regional_level']
    tc_code = telecom_circle['tc_code']
    gid_level = 'GID_{}'.format(level)

    path_output = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regional_data.csv')

    # if os.path.exists(path_output):
    #     return print('Regional data already exists')

    print('Getting regional coverage')
    coverage = process_regional_coverage(telecom_circle)

    print('----')
    print('working on {}'.format(iso3))

    path_night_lights = os.path.join(DATA_INTERMEDIATE, iso3, tc_code,
        'night_lights.tif')
    path_settlements = os.path.join(DATA_INTERMEDIATE, iso3, tc_code,
        'settlements.tif')

    filename = 'regions_{}_{}.shp'.format(level, tc_code)
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
    path = os.path.join(folder, filename)

    regions = gpd.read_file(path)

    results = []

    for index, region in regions.iterrows():

        with rasterio.open(path_night_lights) as src:

            affine = src.transform
            array = src.read(1)
            array[array <= 0] = 0

            luminosity_summation = [d['sum'] for d in zonal_stats(
                region['geometry'],
                array,
                stats=['sum'],
                nodata=0,
                affine=affine)][0]

        with rasterio.open(path_settlements) as src:

            affine = src.transform
            array = src.read(1)
            array[array <= 0] = 0

            population_summation = [d['sum'] for d in zonal_stats(
                region['geometry'],
                array,
                stats=['sum'],
                nodata=0,
                affine=affine)][0]

        area_km2 = round(area_of_polygon(region['geometry']) / 1e6)

        if luminosity_summation == None:
            luminosity_summation = 0

        if area_km2 > 0:
            mean_luminosity_km2 = (
                luminosity_summation / area_km2 if luminosity_summation else 0)
            population_km2 = (
                population_summation / area_km2 if population_summation else 0)
        else:
            mean_luminosity_km2 = 0
            population_km2 = 0

        if 'GSM' in [c for c in coverage.keys()]:
            if region[gid_level] in coverage['GSM']:
                 coverage_GSM_km2 = coverage['GSM'][region[gid_level]]
            else:
                coverage_GSM_km2 = 0
        else:
            coverage_GSM_km2 = 0

        if '3G' in [c for c in coverage.keys()]:
            if region[gid_level] in coverage['3G']:
                coverage_3G_km2 = coverage['3G'][region[gid_level]]
            else:
                coverage_3G_km2 = 0
        else:
            coverage_3G_km2 = 0

        if '4G' in [c for c in coverage.keys()]:
            if region[gid_level] in coverage['4G']:
                coverage_4G_km2 = coverage['4G'][region[gid_level]]
            else:
                coverage_4G_km2 = 0
        else:
            coverage_4G_km2 = 0

        results.append({
            'GID_0': region['GID_0'],
            'GID_id': region[gid_level],
            'GID_level': gid_level,
            'mean_luminosity_km2': mean_luminosity_km2,
            'population': population_summation,
            'area_km2': area_km2,
            'population_km2': population_km2,
            'coverage_GSM_percent': round(coverage_GSM_km2 / area_km2 * 100 if coverage_GSM_km2 else 0, 1),
            'coverage_3G_percent': round(coverage_3G_km2 / area_km2 * 100 if coverage_3G_km2 else 0, 1),
            'coverage_4G_percent': round(coverage_4G_km2 / area_km2 * 100 if coverage_4G_km2 else 0, 1),
        })

    print('Working on backhaul')
    backhaul_lut = estimate_backhaul(telecom_circle['region'], '2025')

    print('Working on estimating sites')
    results = estimate_sites(results, tc_code, backhaul_lut)

    results_df = pd.DataFrame(results)

    results_df.to_csv(path_output, index=False)

    print('Completed {}'.format(tc_code))

    return print('Completed night lights data querying')


def estimate_sites(data, tc_code, backhaul_lut):
    """

    """
    output = []

    population = 0

    for region in data:

        if region['population'] == None:
            continue

        population += int(region['population'])

    path = os.path.join(DATA_RAW, 'telecom_circle_data.csv')
    coverage = pd.read_csv(path)
    coverage = coverage.loc[coverage['tc_code'] == tc_code]
    coverage = coverage['coverage_pop_percentage'].values[0]

    population_covered = int(population) * (float(coverage) / 100)

    #Use tower counts by telecom circle
    path = os.path.join(DATA_RAW, 'ind_sites_by_tc.csv')
    towers = pd.read_csv(path)
    towers = towers.loc[towers['tc_code'] == tc_code]
    towers = towers['sites'].values[0]

    towers_per_pop = towers / population_covered

    tower_backhaul_lut = estimate_backhaul_type(backhaul_lut)

    data = sorted(data, key=lambda k: k['population_km2'], reverse=True)

    covered_pop_so_far = 0

    for region in data:

        if covered_pop_so_far < population_covered:
            sites_estimated_total = int(round(region['population'] * towers_per_pop))
            sites_estimated_km2 = region['population_km2'] * towers_per_pop

        else:
            sites_estimated_total = 0
            sites_estimated_km2 = 0

        backhaul_fiber = 0
        backhaul_copper = 0
        backhaul_wireless = 0
        backhaul_satellite = 0

        for i in range(1, int(round(sites_estimated_total)) + 1):

            num = random.uniform(0, 1)

            if num <= tower_backhaul_lut['fiber']:
                backhaul_fiber += 1
            elif tower_backhaul_lut['fiber'] < num <= tower_backhaul_lut['copper']:
                backhaul_copper += 1
            elif tower_backhaul_lut['copper'] < num <= tower_backhaul_lut['wireless']:
                backhaul_wireless += 1
            elif tower_backhaul_lut['wireless'] < num:
                backhaul_satellite += 1

        output.append({
                'GID_0': region['GID_0'],
                'GID_id': region['GID_id'],
                'GID_level': region['GID_level'],
                'mean_luminosity_km2': region['mean_luminosity_km2'],
                'population': region['population'],
                'area_km2': region['area_km2'],
                'population_km2': region['population_km2'],
                'coverage_GSM_percent': region['coverage_GSM_percent'],
                'coverage_3G_percent': region['coverage_3G_percent'],
                'coverage_4G_percent': region['coverage_4G_percent'],
                'sites_estimated_total': sites_estimated_total,
                'sites_estimated_km2': sites_estimated_km2,
                'sites_3G': int(round(sites_estimated_total * (region['coverage_3G_percent'] /100))),
                'sites_4G': int(round(sites_estimated_total * (region['coverage_4G_percent'] /100))),
                'backhaul_fiber': backhaul_fiber,
                'backhaul_copper': backhaul_copper,
                'backhaul_wireless': backhaul_wireless,
                'backhaul_satellite': backhaul_satellite,
            })

        if region['population'] == None:
            continue

        covered_pop_so_far += region['population']

    return output


def estimate_backhaul(region, year):
    """

    """
    output = []

    path = os.path.join(BASE_PATH, 'raw', 'gsma', 'backhaul.csv')
    backhaul_lut = pd.read_csv(path)
    backhaul_lut = backhaul_lut.to_dict('records')

    for item in backhaul_lut:
        if region == item['Region'] and int(item['Year']) == int(year):
            output.append({
                'tech': item['Technology'],
                'percentage': int(item['Value']),
            })

    return output


def estimate_backhaul_type(backhaul_lut):
    """
    Estimate backhaul type.

    """
    output = {}

    preference = [
        'fiber',
        'copper',
        'wireless',
        'satellite'
    ]

    perc_so_far = 0

    for tech in preference:
        for item in backhaul_lut:
            if tech == item['tech'].lower():
                perc = item['percentage']
                output[tech] = (perc + perc_so_far) / 100
                perc_so_far += perc

    return output


def area_of_polygon(geom):
    """
    Returns the area of a polygon. Assume WGS84 as crs.

    """
    geod = pyproj.Geod(ellps="WGS84")

    poly_area, poly_perimeter = geod.geometry_area_perimeter(
        geom
    )

    return abs(poly_area)


def length_of_line(geom):
    """
    Returns the length of a linestring. Assume WGS84 as crs.

    """
    geod = pyproj.Geod(ellps="WGS84")

    total_length = geod.line_length(*geom.xy)

    return abs(total_length)


def estimate_numers_of_sites(linear_regressor, x_value):
    """
    Function to predict the y value from the stated x value.

    Parameters
    ----------
    linear_regressor : object
        Linear regression object.
    x_value : float
        The stated x value we want to use to predict y.

    Returns
    -------
    result : float
        The predicted y value.

    """
    if not x_value == 0:
        result = linear_regressor.predict(x_value)
        result = result[0,0]
    else:
        result = 0

    return result


def exclude_small_shapes(x):
    """
    Remove small multipolygon shapes.

    Parameters
    ---------
    x : polygon
        Feature to simplify.

    Returns
    -------
    MultiPolygon : MultiPolygon
        Shapely MultiPolygon geometry without tiny shapes.

    """
    # if its a single polygon, just return the polygon geometry
    if x.geometry.geom_type == 'Polygon':
        return x.geometry

    # if its a multipolygon, we start trying to simplify
    # and remove shapes if its too big.
    elif x.geometry.geom_type == 'MultiPolygon':

        area1 = 0.01
        area2 = 50

        # dont remove shapes if total area is already very small
        if x.geometry.area < area1:
            return x.geometry
        # remove bigger shapes if country is really big

        if x['GID_0'] in ['CHL','IDN']:
            threshold = 0.01
        elif x['GID_0'] in ['RUS','GRL','CAN','USA']:
            threshold = 0.01

        elif x.geometry.area > area2:
            threshold = 0.1
        else:
            threshold = 0.001

        # save remaining polygons as new multipolygon for
        # the specific country
        new_geom = []
        for y in x.geometry:
            if y.area > threshold:
                new_geom.append(y)

        return MultiPolygon(new_geom)


def clean_coverage(x):
    """
    Cleans the coverage polygons by remove small multipolygon shapes.

    Parameters
    ---------
    x : polygon
        Feature to simplify.

    Returns
    -------
    MultiPolygon : MultiPolygon
        Shapely MultiPolygon geometry without tiny shapes.

    """
    # if its a single polygon, just return the polygon geometry
    if x.geometry.geom_type == 'Polygon':
        if x.geometry.area > 1e7:
            return x.geometry

    # if its a multipolygon, we start trying to simplify and
    # remove shapes if its too big.
    elif x.geometry.geom_type == 'MultiPolygon':

        threshold = 1e7

        # save remaining polygons as new multipolygon for
        # the specific country
        new_geom = []
        for y in x.geometry:

            if y.area > threshold:
                new_geom.append(y)

        return MultiPolygon(new_geom)


def estimate_core_nodes(iso3, pop_density_km2, settlement_size):
    """
    This function identifies settlements which exceed a desired settlement
    size. It is assumed fiber exists at settlements over, for example,
    20,000 inhabitants.

    Parameters
    ----------
    iso3 : string
        ISO 3 digit country code.
    pop_density_km2 : int
        Population density threshold for identifying built up areas.
    settlement_size : int
        Overall sittelement size assumption, e.g. 20,000 inhabitants.

    Returns
    -------
    output : list of dicts
        Identified major settlements as Geojson objects.

    """
    path = os.path.join(DATA_INTERMEDIATE, iso3, 'settlements.tif')

    with rasterio.open(path) as src:
        data = src.read()
        threshold = pop_density_km2
        data[data < threshold] = 0
        data[data >= threshold] = 1
        polygons = rasterio.features.shapes(data, transform=src.transform)
        shapes_df = gpd.GeoDataFrame.from_features(
            [
                {'geometry': poly, 'properties':{'value':value}}
                for poly, value in polygons
                if value > 0
            ],
            crs='epsg:4326'
        )

    stats = zonal_stats(shapes_df['geometry'], path, stats=['count', 'sum'])

    stats_df = pd.DataFrame(stats)

    nodes = pd.concat([shapes_df, stats_df], axis=1).drop(columns='value')

    nodes = nodes[nodes['sum'] >= settlement_size]

    nodes['geometry'] = nodes['geometry'].centroid

    nodes = get_points_inside_country(nodes, iso3)

    output = []

    for index, item in enumerate(nodes.to_dict('records')):
        output.append({

            'type': 'Feature',
            'geometry': mapping(item['geometry']),
            'properties': {
                'network_layer': 'core',
                'id': 'core_{}'.format(index),
                'node_number': index,
            }
        })

    return output


def get_points_inside_country(nodes, iso3):
    """
    Check settlement locations lie inside target country.

    Parameters
    ----------
    nodes : dataframe
        A geopandas dataframe containing settlement nodes.
    iso3 : string
        ISO 3 digit country code.

    Returns
    -------
    nodes : dataframe
        A geopandas dataframe containing settlement nodes.

    """
    filename = 'tc_outline.shp'
    path = os.path.join(DATA_INTERMEDIATE, iso3, filename)

    national_outline = gpd.read_file(path)

    bool_list = nodes.intersects(national_outline.unary_union)

    nodes = pd.concat([nodes, bool_list], axis=1)

    nodes = nodes[nodes[0] == True].drop(columns=0)

    return nodes


def generate_agglomeration_lut(telecom_circle):
    """
    Generate a lookup table of agglomerations.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.

    """
    iso3 = telecom_circle['iso3']
    regional_level = telecom_circle['regional_level']
    GID_level = 'GID_{}'.format(regional_level)
    tc_code = telecom_circle['tc_code']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations')
    if not os.path.exists(folder):
        os.makedirs(folder)
    path_output = os.path.join(folder, 'agglomerations.shp')

    # if os.path.exists(path_output):
    #     return print('Agglomeration processing has already completed')

    print('Working on {} agglomeration lookup table'.format(tc_code))

    filename = 'regions_{}_{}.shp'.format(regional_level, tc_code)
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
    path = os.path.join(folder, filename)
    regions = gpd.read_file(path, crs="epsg:4326")

    path_settlements = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'settlements.tif')
    settlements = rasterio.open(path_settlements, 'r+')
    settlements.nodata = 255
    settlements.crs = {"epsg:4326"}

    folder_tifs = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations', 'tifs')
    if not os.path.exists(folder_tifs):
        os.makedirs(folder_tifs)

    for idx, region in regions.iterrows():

        bbox = region['geometry'].envelope
        geo = gpd.GeoDataFrame()
        geo = gpd.GeoDataFrame({'geometry': bbox}, index=[idx])
        coords = [json.loads(geo.to_json())['features'][0]['geometry']]

        #chop on coords
        out_img, out_transform = mask(settlements, coords, crop=True)

        # Copy the metadata
        out_meta = settlements.meta.copy()

        out_meta.update({"driver": "GTiff",
                        "height": out_img.shape[1],
                        "width": out_img.shape[2],
                        "transform": out_transform,
                        "crs": 'epsg:4326'})

        path_output = os.path.join(folder_tifs, region[GID_level] + '.tif')

        with rasterio.open(path_output, "w", **out_meta) as dest:
                dest.write(out_img)

    print('Completed settlement.tif regional segmentation')

    nodes, missing_nodes = find_nodes(telecom_circle, regions)

    missing_nodes = get_missing_nodes(telecom_circle, regions, missing_nodes, 10, 10)

    nodes = nodes + missing_nodes

    nodes = gpd.GeoDataFrame.from_features(nodes, crs='epsg:4326')

    bool_list = nodes.intersects(regions['geometry'].unary_union)
    nodes = pd.concat([nodes, bool_list], axis=1)
    nodes = nodes[nodes[0] == True].drop(columns=0)

    agglomerations = []

    print('Identifying agglomerations')
    for idx1, region in regions.iterrows():

        if 'GID_1' in region:
            GID_1 = region['GID_1']
        else:
            GID_1 = ''
        if 'GID_2' in region:
            GID_2 = region['GID_2']
        else:
            GID_2 = ''
        if 'GID_3' in region:
            GID_3 = region['GID_3']
        else:
            GID_3 = ''

        seen = set()

        for idx2, node in nodes.iterrows():
            if node['geometry'].intersects(region['geometry']):
                agglomerations.append({
                    'type': 'Feature',
                    'geometry': mapping(node['geometry']),
                    'properties': {
                        'id': idx1,
                        'GID_0': region['GID_0'],
                        'GID_1': GID_1,
                        'GID_2': GID_2,
                        'GID_3': GID_3,
                        # GID_level: region[GID_level],
                        'population': node['sum'],
                    }
                })
                seen.add(region[GID_level])
        if len(seen) == 0:
            agglomerations.append({
                    'type': 'Feature',
                    'geometry': mapping(region['geometry'].centroid),
                    'properties': {
                        'id': 'regional_node',
                        'GID_0': region['GID_0'],
                        'GID_1': GID_1,
                        'GID_2': GID_2,
                        'GID_3': GID_3,
                        # GID_level: region[GID_level],
                        'population': 1,
                    }
                })

    agglomerations = gpd.GeoDataFrame.from_features(
            [
                {
                    'geometry': item['geometry'],
                    'properties': {
                        'id': item['properties']['id'],
                        'GID_0': item['properties']['GID_0'],
                        'GID_1': item['properties']['GID_1'],
                        'GID_2': item['properties']['GID_2'],
                        'GID_3': item['properties']['GID_3'],
                        # GID_level: item['properties'][GID_level],
                        'population': item['properties']['population'],
                    }
                }
                for item in agglomerations
            ],
            crs='epsg:4326'
        )

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations')
    path_output = os.path.join(folder, 'agglomerations' + '.shp')

    agglomerations.to_file(path_output)

    agglomerations['lon'] = agglomerations['geometry'].x
    agglomerations['lat'] = agglomerations['geometry'].y
    agglomerations = agglomerations[['lon', 'lat', GID_level, 'population']]
    agglomerations.to_csv(os.path.join(folder, 'agglomerations.csv'), index=False)

    return print('Agglomerations layer complete')


def process_existing_fiber(telecom_circle):
    """
    Load and process existing fiber data.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    regional_level = telecom_circle['regional_level']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network_existing')
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = 'core_edges_existing.shp'
    path_output = os.path.join(folder, filename)

    # if os.path.exists(path_output):
    #     return print('Existing fiber already processed')

    path = os.path.join(DATA_RAW, 'rail_fiber_routes', 'IND_rails.shp')
    data = gpd.read_file(path, crs='epsg:4326')
    data['source'] = 'existing'

    filename = 'regions_{}_{}.shp'.format(regional_level, tc_code)
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
    path = os.path.join(folder, filename)
    regions = gpd.read_file(path, crs="epsg:4326")

    data = gpd.clip(regions, data)
    data.to_file(path_output, crs='epsg:4326')

    return print('Existing fiber processed')


def find_nodes_on_existing_infrastructure(telecom_circle):
    """
    Find those agglomerations which are within a buffered zone of
    existing fiber links.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network_existing')
    filename = 'core_nodes_existing.shp'
    path_output = os.path.join(folder, filename)

    # if os.path.exists(path_output):
    #     return print('Already found nodes on existing infrastructure')
    # else:
    #     if not os.path.dirname(path_output):
    #         os.makedirs(os.path.dirname(path_output))

    path = os.path.join(folder, 'core_edges_existing.shp')
    if not os.path.exists(path):
        return print('No existing infrastructure')

    existing_infra = gpd.read_file(path, crs='epsg:4326')

    existing_infra = existing_infra.to_crs(epsg=3857)
    existing_infra['geometry'] = existing_infra['geometry'].buffer(5000)
    existing_infra = existing_infra.to_crs(epsg=4326)

    filename = 'agglomerations.shp'
    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations', filename)
    agglomerations = gpd.read_file(path, crs='epsg:4326')

    bool_list = agglomerations.intersects(existing_infra.unary_union)

    agglomerations = pd.concat([agglomerations, bool_list], axis=1)

    agglomerations = agglomerations[agglomerations[0] == True].drop(columns=0)

    agglomerations['source'] = 'existing'

    agglomerations.to_file(path_output, crs='epsg:4326')

    return print('Found nodes on existing infrastructure')


def find_nodes(telecom_circle, regions):
    """
    Find key nodes.

    Some regions fail because the population threshold is set too high.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    regional_level = telecom_circle['regional_level']
    GID_level = 'GID_{}'.format(regional_level)

    threshold = telecom_circle['pop_density_km2']
    settlement_size = telecom_circle['settlement_size']

    folder_tifs = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations', 'tifs')

    interim = []
    missing_nodes = set()

    print('Working on gathering data from regional rasters')
    for idx, region in regions.iterrows():

        path = os.path.join(folder_tifs, region[GID_level] + '.tif')

        with rasterio.open(path) as src:
            data = src.read()
            data[data < threshold] = 0
            data[data >= threshold] = 1
            polygons = rasterio.features.shapes(data, transform=src.transform)
            shapes_df = gpd.GeoDataFrame.from_features(
                [
                    {'geometry': poly, 'properties':{'value':value}}
                    for poly, value in polygons
                    if value > 0
                ],
                crs='epsg:4326'
            )

        geojson_region = [
            {
                'geometry': region['geometry'],
                'properties': {
                    GID_level: region[GID_level]
                }
            }
        ]

        gpd_region = gpd.GeoDataFrame.from_features(
                [
                    {'geometry': poly['geometry'],
                    'properties':{
                        GID_level: poly['properties'][GID_level]
                        }}
                    for poly in geojson_region
                ], crs='epsg:4326'
            )

        if len(shapes_df) == 0:
            print('WARNING: No possible nodes locations found')
            print('WARNING: May need to check the regional population density threshold')
            continue

        nodes = gpd.overlay(shapes_df, gpd_region, how='intersection')

        stats = zonal_stats(shapes_df['geometry'], path, stats=['count', 'sum'])

        stats_df = pd.DataFrame(stats)

        nodes = pd.concat([shapes_df, stats_df], axis=1).drop(columns='value')

        nodes_subset = nodes[nodes['sum'] >= settlement_size]

        if len(nodes_subset) == 0:
            missing_nodes.add(region[GID_level])

        for idx, item in nodes_subset.iterrows():
            interim.append({
                    'geometry': item['geometry'].centroid,
                    'properties': {
                        GID_level: region[GID_level],
                        'count': item['count'],
                        'sum': item['sum']
                    }
            })

    return interim, missing_nodes


def get_missing_nodes(telecom_circle, regions, missing_nodes, threshold, settlement_size):
    """
    Find any missing nodes

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    regional_level = telecom_circle['regional_level']
    GID_level = 'GID_{}'.format(regional_level)

    folder_tifs = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'agglomerations', 'tifs')

    interim = []

    for idx, region in regions.iterrows():

        if not region[GID_level] in list(missing_nodes):
            continue

        path = os.path.join(folder_tifs, region[GID_level] + '.tif')

        with rasterio.open(path) as src:
            data = src.read()
            data[data < threshold] = 0
            data[data >= threshold] = 1
            polygons = rasterio.features.shapes(data, transform=src.transform)
            shapes_df = gpd.GeoDataFrame.from_features(
                [
                    {'geometry': poly, 'properties':{'value':value}}
                    for poly, value in polygons
                    if value > 0
                ],
                crs='epsg:4326'
            )

        geojson_region = [
            {
                'geometry': region['geometry'],
                'properties': {
                    GID_level: region[GID_level]
                }
            }
        ]

        gpd_region = gpd.GeoDataFrame.from_features(
                [
                    {'geometry': poly['geometry'],
                    'properties':{
                        GID_level: poly['properties'][GID_level]
                        }}
                    for poly in geojson_region
                ], crs='epsg:4326'
            )

        nodes = gpd.overlay(shapes_df, gpd_region, how='intersection')

        stats = zonal_stats(shapes_df['geometry'], path, stats=['count', 'sum'])

        stats_df = pd.DataFrame(stats)

        nodes = pd.concat([shapes_df, stats_df], axis=1).drop(columns='value')

        max_sum = nodes['sum'].max()

        nodes = nodes[nodes['sum'] > max_sum - 1]

        for idx, item in nodes.iterrows():
            interim.append({
                    'geometry': item['geometry'].centroid,
                    'properties': {
                        GID_level: region[GID_level],
                        'count': item['count'],
                        'sum': item['sum']
                    }
            })

    return interim


def find_regional_nodes(telecom_circle):
    """

    """
    iso3 = telecom_circle['iso3']
    regional_level = telecom_circle['regional_level']
    # GID_level = 'GID_{}'.format(regional_level)
    GID_level = 'GID_{}'.format(2)
    tc_code = telecom_circle['tc_code']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)
    input_path = os.path.join(folder, 'agglomerations', 'agglomerations.shp')
    existing_nodes_path = os.path.join(folder, 'network_existing', 'core_nodes_existing.shp')
    output_path = os.path.join(folder, 'network', 'core_nodes.shp')
    regional_output_path = os.path.join(folder, 'network', 'regional_nodes')

    regions = gpd.read_file(input_path, crs="epsg:4326")

    unique_regions = regions[GID_level].unique()

    # if os.path.exists(output_path):
    #     return print('Regional nodes layer already generated')

    folder = os.path.dirname(output_path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    if not os.path.exists(regional_output_path):
        os.makedirs(regional_output_path)

    interim = []

    for unique_region in unique_regions:
        agglomerations = []
        for idx, region in regions.iterrows():
            if unique_region == region[GID_level]:
                agglomerations.append({
                    'type': 'Feature',
                    'geometry': region['geometry'],
                    'properties': {
                        GID_level: region[GID_level],
                        'population': region['population'],
                        'source': 'existing',
                    }
                })

        regional_nodes = gpd.GeoDataFrame.from_features(agglomerations, crs='epsg:4326')
        path = os.path.join(regional_output_path, unique_region + '.shp')
        regional_nodes.to_file(path)

        agglomerations = sorted(agglomerations, key=lambda k: k['properties']['population'], reverse=True)

        interim.append(agglomerations[0])

    if os.path.exists(existing_nodes_path):

        output = []
        new_nodes = []
        seen = set()

        existing_nodes = gpd.read_file(existing_nodes_path, crs='epsg:4326')
        existing_nodes = existing_nodes.to_dict('records')

        for item in existing_nodes:
            seen.add(item[GID_level])
            output.append({
                'type': 'Point',
                'geometry': mapping(item['geometry']),
                'properties': {
                    GID_level: item[GID_level],
                    'population': item['population'],
                    'source': 'existing',
                }
            })

        for item in interim:
            if not item['properties'][GID_level] in seen:
                new_node = {
                    'type': 'Point',
                    'geometry': mapping(item['geometry']),
                    'properties': {
                        GID_level: item['properties'][GID_level],
                        'population': item['properties']['population'],
                        'source': 'new',
                    }
                }
                output.append(new_node)
                new_nodes.append(new_node)

        output = gpd.GeoDataFrame.from_features(output)
        output.to_file(output_path, crs='epsg:4326')#write core nodes

        if len(new_nodes) > 0:
            new_nodes = gpd.GeoDataFrame.from_features(new_nodes)
            path = os.path.join(DATA_INTERMEDIATE, iso3, 'network', 'new_nodes.shp')
            new_nodes.to_file(path, crs='epsg:4326')#write core nodes

    if not os.path.exists(output_path):

        output = gpd.GeoDataFrame.from_features(
            [
                {'geometry': item['geometry'], 'properties': item['properties']}
                for item in interim
            ],
            crs='epsg:4326'
        )
        output['source'] = 'new'
        output.to_file(output_path)#write core nodes

    output = []

    for unique_region in unique_regions:

        path = os.path.join(regional_output_path, unique_region + '.shp')
        if os.path.exists(path):
            regional_nodes = gpd.read_file(path, crs='epsg:4326')

            for idx, regional_node in regional_nodes.iterrows():
                output.append({
                    'geometry': regional_node['geometry'],
                    'properties': {
                        'value': regional_node['population'],
                        'source': 'new',
                    }
                })

    output = gpd.GeoDataFrame.from_features(output, crs='epsg:4326')
    path = os.path.join(folder, 'regional_nodes.shp')
    output.to_file(path)

    return print('Completed regional node estimation')


def fit_edges(input_path, output_path):
    """
    Fit edges to nodes using a minimum spanning tree.

    Parameters
    ----------
    path : string
        Path to nodes shapefile.

    """
    folder = os.path.dirname(output_path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    nodes = gpd.read_file(input_path, crs='epsg:4326')
    nodes = nodes.to_crs('epsg:3857')

    all_possible_edges = []

    for node1_id, node1 in nodes.iterrows():
        for node2_id, node2 in nodes.iterrows():
            if node1_id != node2_id:
                geom1 = shape(node1['geometry'])
                geom2 = shape(node2['geometry'])
                line = LineString([geom1, geom2])
                all_possible_edges.append({
                    'type': 'Feature',
                    'geometry': mapping(line),
                    'properties':{
                        # 'network_layer': 'core',
                        'from': node1_id,
                        'to':  node2_id,
                        'length': line.length,
                        'source': 'new',
                    }
                })

    if len(all_possible_edges) == 0:
        return

    G = nx.Graph()

    for node_id, node in enumerate(nodes):
        G.add_node(node_id, object=node)

    for edge in all_possible_edges:
        G.add_edge(edge['properties']['from'], edge['properties']['to'],
            object=edge, weight=edge['properties']['length'])

    tree = nx.minimum_spanning_edges(G)

    edges = []

    for branch in tree:
        link = branch[2]['object']
        if link['properties']['length'] > 0:
            edges.append(link)

    edges = gpd.GeoDataFrame.from_features(edges, crs='epsg:3857')

    if len(edges) > 0:
        edges = edges.to_crs('epsg:4326')
        edges.to_file(output_path)

    return


def prepare_edge_fitting(telecom_circle):
    """

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)
    core_edges_path = os.path.join(folder, 'network_existing', 'core_edges_existing.shp')

    if not os.path.exists(core_edges_path):

        input_path = os.path.join(folder, 'network', 'core_nodes.shp')
        output_path = os.path.join(folder, 'network', 'core_edges.shp')
        fit_edges(input_path, output_path)

    else:

        core_nodes_path = os.path.join(folder, 'network_existing', 'core_nodes_existing.shp')
        existing_nodes = gpd.read_file(core_nodes_path, crs='epsg:4326')
        path = os.path.join(folder, 'network', 'new_nodes.shp')

        output = []

        if os.path.exists(path):

            new_nodes = gpd.read_file(path, crs='epsg:4326')

            for idx, new_node in new_nodes.iterrows():

                nearest = nearest_points(new_node.geometry, existing_nodes.unary_union)[1]

                geom = LineString([
                            (
                                new_node['geometry'].coords[0][0],
                                new_node['geometry'].coords[0][1]
                            ),
                            (
                                nearest.coords[0][0],
                                nearest.coords[0][1]
                            ),
                        ])

                output.append({
                    'type': 'LineString',
                    'geometry': mapping(geom),
                    'properties': {
                        'id': idx,
                        'source': 'new'
                    }
                })

        existing_edges = gpd.read_file(core_edges_path, crs='epsg:4326')

        for idx, existing_edge in existing_edges.iterrows():
            output.append({
                'type': 'LineString',
                'geometry': mapping(existing_edge['geometry']),
                'properties': {
                    'id': idx,
                    'source': 'existing'
                }
            })

        output = gpd.GeoDataFrame.from_features(output)
        path = os.path.join(folder, 'network', 'core_edges.shp')
        output.to_file(path, crs='epsg:4326')


def fit_regional_edges(telecom_circle):
    """

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']
    regional_level = telecom_circle['regional_level']
    GID_level = 'GID_{}'.format(2)

    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network')
    path = os.path.join(folder, 'core_nodes.shp')

    nodes = gpd.read_file(path, crs="epsg:4326")
    unique_regions = nodes[GID_level].unique()

    for unique_region in unique_regions:
        input_path = os.path.join(folder, 'regional_nodes', unique_region + '.shp')
        output_path = os.path.join(folder, 'regional_edges', unique_region + '.shp')
        fit_edges(input_path, output_path)

    output = []

    for unique_region in unique_regions:

        path = os.path.join(folder, 'regional_edges', unique_region + '.shp')
        if os.path.exists(path):
            regional_edges = gpd.read_file(path, crs='epsg:4326')

            for idx, regional_edge in regional_edges.iterrows():
                output.append({
                    'geometry': regional_edge['geometry'],
                    'properties': {
                        'value': regional_edge['length'],
                        'source': 'new',
                    }
                })

    if len(output) > 0:
        output = gpd.GeoDataFrame.from_features(output, crs='epsg:4326')
        path = os.path.join(folder, 'regional_edges.shp')
        output.to_file(path)
    else:
        print('----WARNING--- No regional edges exist for {}'.format(tc_code))

    return print('Regional edge fitting complete')


def generate_core_lut(telecom_circle):
    """
    Generate core lut.

    """
    iso3 = telecom_circle['iso3']
    level = telecom_circle['regional_level']
    tc_code = telecom_circle['tc_code']
    regional_level = 'GID_{}'.format(level)

    filename = 'core_lut.csv'
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code)
    output_path = os.path.join(folder, filename)

    # if os.path.exists(output_path):
    #     return print('Core LUT already generated')

    filename = 'regions_{}_{}.shp'.format(level, tc_code)
    folder = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'regions')
    path = os.path.join(folder, filename)
    regions = gpd.read_file(path)
    regions.crs = 'epsg:4326'

    output = []

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network', 'core_edges.shp')
    core_edges = gpd.read_file(path)
    core_edges.crs = 'epsg:4326'
    core_edges = gpd.GeoDataFrame(
        {'geometry': core_edges['geometry'], 'source': core_edges['source']})

    existing_edges = core_edges.loc[core_edges['source'] == 'existing']
    existing_edges = gpd.clip(regions, existing_edges)
    existing_edges = existing_edges.to_crs('epsg:3857')
    existing_edges['length'] = existing_edges['geometry'].length

    for idx, edge in existing_edges.iterrows():
        output.append({
            'GID_id': edge[regional_level],
            'asset': 'core_edge',
            'value': edge['length'],
            'source': 'existing',
        })

    new_edges = core_edges.loc[core_edges['source'] == 'new']
    new_edges = gpd.clip(regions, new_edges)
    new_edges = new_edges.to_crs('epsg:3857')
    new_edges['length'] = new_edges['geometry'].length

    for idx, edge in new_edges.iterrows():
        output.append({
            'GID_id': edge[regional_level],
            'asset': 'core_edge',
            'value': edge['length'],
            'source': 'new',
        })


    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network', 'regional_edges.shp')
    if os.path.exists(path):
        regional_edges = gpd.read_file(path, crs='epsg:4326')

        regional_edges = gpd.clip(regions, regional_edges)
        regional_edges = regional_edges.to_crs('epsg:3857')
        regional_edges['length'] = regional_edges['geometry'].length

        for idx, edge in regional_edges.iterrows():
            output.append({
                'GID_id': edge[regional_level],
                'asset': 'regional_edge',
                'value': edge['length'],
                'source': 'new', #all regional edges are assumed to be new
            })

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network', 'core_nodes.shp')
    nodes = gpd.read_file(path, crs='epsg:4326')

    existing_nodes = nodes.loc[nodes['source'] == 'existing']
    f = lambda x:np.sum(existing_nodes.intersects(x))
    regions['nodes'] = regions['geometry'].apply(f)

    for idx, region in regions.iterrows():
        output.append({
            'GID_id': region[regional_level],
            'asset': 'core_node',
            'value': region['nodes'],
            'source': 'existing',
        })

    new_nodes = nodes.loc[nodes['source'] == 'new']
    f = lambda x:np.sum(new_nodes.intersects(x))
    regions['nodes'] = regions['geometry'].apply(f)

    for idx, region in regions.iterrows():
        output.append({
            'GID_id': region[regional_level],
            'asset': 'core_node',
            'value': region['nodes'],
            'source': 'new',
        })

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'network', 'regional_nodes.shp')
    regional_nodes = gpd.read_file(path, crs='epsg:4326')

    existing_nodes = regional_nodes.loc[regional_nodes['source'] == 'existing']
    f = lambda x:np.sum(existing_nodes.intersects(x))
    regions['regional_nodes'] = regions['geometry'].apply(f)

    for idx, region in regions.iterrows():
        output.append({
            'GID_id': region[regional_level],
            'asset': 'regional_node',
            'value': region['regional_nodes'],
            'source': 'existing',
        })

    new_nodes = regional_nodes.loc[regional_nodes['source'] == 'new']
    f = lambda x:np.sum(new_nodes.intersects(x))
    regions['regional_nodes'] = regions['geometry'].apply(f)

    for idx, region in regions.iterrows():
        output.append({
            'GID_id': region[regional_level],
            'asset': 'regional_node',
            'value': region['regional_nodes'],
            'source': 'new',
        })

    output = pd.DataFrame(output)
    output = output.drop_duplicates()
    output.to_csv(output_path, index=False)

    return print('Completed core lut')


def load_subscription_data(path, telecom_circle):
    """
    Load in cell phone subscription data.

    Parameters
    ----------
    path : string
        Location of itu data as .csv.
    telecom_circle : string
        Telecom circle data.

    Returns
    -------
    output :
        Time series data of cell phone subscriptions.

    """
    output = []

    historical_data = pd.read_csv(path)
    historical_data = historical_data.to_dict('records')

    for year in range(2008, 2018+1):
        year = str(year)
        for item in historical_data:
            if item['tc_code'] == telecom_circle['tc_code']:

                penetration = float(item[year])

                if telecom_circle['tc_code'] in ['UE', 'UW']:
                    penetration = penetration / 2

                output.append({
                    'tc_code': telecom_circle['tc_code'],
                    'category': telecom_circle['category'],
                    'penetration': penetration,
                    'year': year,
                })

    return output


def forecast_subscriptions(telecom_circle):
    """

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']

    path = os.path.join(DATA_RAW, 'ten_year_subsc_data.csv')
    historical_data = load_subscription_data(path, telecom_circle)

    start_point = 2019
    end_point = 2030
    horizon = 4

    forecast = forecast_linear(
        telecom_circle,
        historical_data,
        start_point,
        end_point,
        horizon
    )

    forecast_df = pd.DataFrame(historical_data + forecast)

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'subscriptions')

    if not os.path.exists(path):
        os.mkdir(path)

    forecast_df.to_csv(os.path.join(path, 'subs_forecast.csv'), index=False)

    path = os.path.join(BASE_PATH, '..', 'vis', 'subscriptions', 'data_inputs')
    forecast_df.to_csv(os.path.join(path, '{}.csv'.format(tc_code)), index=False)

    return print('Completed subscription forecast')


def forecast_linear(telecom_circle, historical_data, start_point, end_point, horizon):
    """
    Forcasts subscription adoption rate.

    Parameters
    ----------
    telecom_circle : dict
        Contains all parameter information for the telecom circle.
    historical_data : list of dicts
        Past penetration data.
    start_point : int
        Starting year of forecast period.
    end_point : int
        Final year of forecast period.
    horizon : int
        Number of years to use to estimate mean growth rate.

    """
    output = []

    subs_growth = telecom_circle['subs_growth']

    year_0 = sorted(historical_data, key = lambda i: i['year'], reverse=True)[0]

    for year in range(start_point, end_point + 1):
        if year == start_point:

            penetration = year_0['penetration'] * (1 + (subs_growth/100))
        else:
            penetration = penetration * (1 + (subs_growth/100))

        if penetration > 95:
            penetration = 95

        if year not in [item['year'] for item in output]:

            output.append({
                'tc_code': telecom_circle['tc_code'],
                'category': telecom_circle['category'],
                'year': year,
                'penetration': round(penetration, 2),
            })

    return output


def forecast_smartphones(telecom_circle):
    """
    Forecast smartphone adoption.
    Parameters
    ----------
    historical_data : list of dicts
        Past penetration data.

    """
    iso3 = telecom_circle['iso3']
    tc_code = telecom_circle['tc_code']

    path = os.path.join(DATA_RAW, 'wb_smartphone_survey', 'wb_smartphone_survey.csv')
    survey_data = load_smartphone_data(path, telecom_circle)

    start_point = 2020
    end_point = 2030

    forecast = forecast_smartphones_linear(
        survey_data,
        telecom_circle,
        start_point,
        end_point
    )

    forecast_df = pd.DataFrame(forecast)

    path = os.path.join(DATA_INTERMEDIATE, iso3, tc_code, 'smartphones')

    if not os.path.exists(path):
        os.mkdir(path)

    forecast_df.to_csv(os.path.join(path, 'smartphone_forecast.csv'), index=False)

    path = os.path.join(BASE_PATH, '..', 'vis', 'smartphones', 'data_inputs')
    if not os.path.exists(path):
        os.mkdir(path)
    forecast_df.to_csv(os.path.join(path, '{}.csv'.format(tc_code)), index=False)

    return print('Completed subscription forecast')


def load_smartphone_data(path, telecom_circle):
    """
    Load smartphone adoption survey data.
    Parameters
    ----------
    path : string
        Location of data as .csv.
    telecom_circle : string
        telecom_circle data.
    """
    survey_data = pd.read_csv(path)

    survey_data = survey_data.to_dict('records')

    countries_with_data = [i['iso3'] for i in survey_data]

    output = []

    if telecom_circle['iso3']  in countries_with_data:
        for item in survey_data:
                if item['iso3'] == telecom_circle['iso3']:
                    output.append({
                        'tc_code': telecom_circle['tc_code'],
                        'category': telecom_circle['category'],
                        'cluster': item['cluster'],
                        'settlement_type': item['Settlement'],
                        'smartphone_penetration': item['Smartphone']
                    })

    else:
        for item in survey_data:
            if item['cluster'] == telecom_circle['cluster']:
                output.append({
                    'tc_code': telecom_circle['tc_code'],
                    'category': telecom_circle['category'],
                    'cluster': item['cluster'],
                    'settlement_type': item['Settlement'],
                    'smartphone_penetration': item['Smartphone']
                })

    return output


def forecast_smartphones_linear(data, telecom_circle, start_point, end_point):
    """
    Forecast smartphone adoption.
    """
    output = []

    smartphone_growth = telecom_circle['sp_growth']

    for item in data:

        for year in range(start_point, end_point + 1):

            if year == start_point:

                penetration = item['smartphone_penetration']

            else:
                penetration = penetration * (1 + (smartphone_growth/100))

            if penetration > 90:
                penetration = 90

            output.append({
                'tc_code': item['tc_code'],
                'category': telecom_circle['category'],
                'settlement_type': item['settlement_type'].lower(),
                'year': year,
                'penetration': round(penetration, 2),
            })

    return output


if __name__ == '__main__':

    tc_lut = {
        'AP':'A',
        'AS':'C',
        'BR':'C',
        'DL':'Metro',
        'GJ':'A',
        'HP':'C',
        'HR':'B',
        'JK':'C',
        'KA':'A',
        'KL':'B',
        'KO':'Metro',
        'MH':'A',
        'MP':'B',
        'MU':'Metro',
        'NE':'C',
        'OR':'C',
        'PB':'B',
        'RJ':'B',
        'TN':'A',
        'UE':'B',
        'UW':'B',
        'WB':'C',
    }

    tc_codes = [
        'AP',
        'AS',
        'BR',
        'DL',
        'GJ',
        'HP',
        'HR',
        'JK',
        'KA',
        'KL',
        'KO',
        'MH',
        'MP',
        'MU',
        'NE',
        'OR',
        'PB',
        'RJ',
        'TN',
        'UE',
        'UW',
        'WB',
    ]

    telecom_circles = []

    tc_thresholds = {
        'AP':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'AS':{'subs_growth': 4, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'BR':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 1000,'settlement_size': 20000},
        'DL':{'subs_growth': 2.5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 1000,'settlement_size': 20000},
        'GJ':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'HP':{'subs_growth': 3, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 1000,'settlement_size': 20000},
        'HR':{'subs_growth': 7, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'JK':{'subs_growth': 5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'KA':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'KL':{'subs_growth': 3, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'KO':{'subs_growth': 3.5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'MH':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'MP':{'subs_growth': 0.5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'MU':{'subs_growth': 3.5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 1000,'settlement_size': 20000},
        'NE':{'subs_growth': 5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'OR':{'subs_growth': 3, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'PB':{'subs_growth': 3, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'RJ':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'TN':{'subs_growth': 0.5, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'UE':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'UW':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
        'WB':{'subs_growth': 2, 'sp_growth': 10, 'regional_level': 3, 'pop_density_km2': 500,'settlement_size': 1000},
    }

    for tc_code in tc_codes:

        if not tc_code in tc_thresholds.keys():
            telecom_circles.append({
                'iso3': 'IND', 'iso2': 'IN', 'tc_code': tc_code, 'category': tc_lut[tc_code],
                'regional_level': 3, 'region': 'S&SE Asia', 'pop_density_km2': 1000,
                'settlement_size': 20000,
                'subs_growth': tc_thresholds[tc_code]['subs_growth'],
                'sp_growth': tc_thresholds[tc_code]['sp_growth'],
            })
        else:
            telecom_circles.append({
                'iso3': 'IND', 'iso2': 'IN', 'tc_code': tc_code, 'category': tc_lut[tc_code],
                'regional_level': tc_thresholds[tc_code]['regional_level'],
                'region': 'S&SE Asia',
                'pop_density_km2': tc_thresholds[tc_code]['pop_density_km2'],
                'settlement_size': tc_thresholds[tc_code]['settlement_size'],
                'subs_growth': tc_thresholds[tc_code]['subs_growth'],
                'sp_growth': tc_thresholds[tc_code]['sp_growth'],
            })

    print('Processing country boundary')
    process_country_shape(telecom_circles[0]['iso3'])

    for tc in telecom_circles:

        print('Working on {}'.format(tc['tc_code']))

        print('--Processing regions')
        process_regions(tc)

        print('--Processing settlement layer')
        process_settlement_layer(tc)

        print('--Processing night lights')
        process_night_lights(tc)

        print('--Processing coverage shapes')
        process_coverage_shapes(tc)

        print('--Getting regional data')
        get_regional_data(tc)

        print('--Generating agglomeration lookup table')
        generate_agglomeration_lut(tc)

        print('--Load existing fiber infrastructure')
        process_existing_fiber(tc)

        print('--Estimate existing nodes')
        find_nodes_on_existing_infrastructure(tc)

        print('--Find regional nodes')
        find_regional_nodes(tc)

        print('--Fit edges')
        prepare_edge_fitting(tc)

        print('--Fit regional edges')
        fit_regional_edges(tc)

        print('--Create core lookup table')
        generate_core_lut(tc)

        print('--Create subscription forcast')
        forecast_subscriptions(tc)

        print('--Forecasting smartphones')
        forecast_smartphones(tc)
