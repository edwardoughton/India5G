import pytest
import math
from india5g.costs import (
    greenfield_4g,
    upgrade_to_4g,
    greenfield_5g_nsa,
    upgrade_to_5g_nsa,
    get_backhaul_costs,
    regional_net_costs,
    core_costs,
    discount_opex,
    discount_capex_and_opex,
    calc_costs,
    find_single_network_cost
)

def test_greenfield_4g(setup_region, setup_option, setup_costs,
    setup_global_parameters, setup_core_lut, setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['new_sites'] = 1
    setup_region[0]['site_density'] = 1

    #test baseline infra sharing
    cost_structure = greenfield_4g(setup_region[0],
        '4G_epc_wireless_baseline_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500
    assert cost_structure['single_remote_radio_unit'] == 4000
    assert cost_structure['io_fronthaul'] ==1500
    assert cost_structure['tower'] == 10000
    assert cost_structure['civil_materials'] == 5000
    assert cost_structure['transportation'] == 5000
    assert cost_structure['installation'] == 5000
    assert cost_structure['site_rental'] == 9600
    assert cost_structure['power_generator_battery_system'] == 5000
    assert cost_structure['io_s1_x2'] == 1500
    assert cost_structure['router'] == 2000

    #test passive infra sharing
    cost_structure = greenfield_4g(setup_region[0],
        '4G_epc_wireless_passive_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['tower'] == 10000 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['civil_materials'] == 5000 / setup_country_parameters['networks']['baseline_urban']

    #test active infra sharing
    cost_structure = greenfield_4g(setup_region[0],
        '4G_epc_wireless_active_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['single_remote_radio_unit'] == 4000 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['bbu_cabinet'] == 500 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['civil_materials'] == 5000 / setup_country_parameters['networks']['baseline_urban']

    setup_region[0]['sites_estimated_total'] = 6
    setup_region[0]['upgraded_sites'] = 3
    setup_region[0]['sites_3G'] = 3
    setup_region[0]['site_density'] = 2

    #test shared wholesale core network
    cost_structure = greenfield_4g(setup_region[0],
        '4G_epc_wireless_shared_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['core_node'] == (
        (setup_costs['core_node_epc'] * 2) /
        (setup_region[0]['sites_estimated_total'] / setup_country_parameters['networks']['baseline_urban'])
        ) / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['regional_node'] == (
        (setup_costs['regional_node_epc'] * 2) /
        (setup_region[0]['sites_estimated_total'] / setup_country_parameters['networks']['baseline_urban'])
        / setup_country_parameters['networks']['baseline_urban'])


def test_upgrade_to_4g(setup_region, setup_option, setup_costs,
    setup_global_parameters, setup_core_lut, setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['upgraded_sites'] = 1
    setup_region[0]['sites_3G'] = 1
    setup_region[0]['site_density'] = 0.5

    cost_structure = upgrade_to_4g(setup_region[0],
        '4G_epc_wireless_baseline_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500
    assert cost_structure['single_remote_radio_unit'] == 4000
    assert cost_structure['installation'] == 5000
    assert cost_structure['site_rental'] == 9600
    assert cost_structure['router'] == 2000

    #test passive infra sharing
    cost_structure = upgrade_to_4g(setup_region[0],
        '4G_epc_wireless_passive_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['site_rental'] == 9600 / setup_country_parameters['networks']['baseline_urban']

    #test active infra sharing
    cost_structure = upgrade_to_4g(setup_region[0],
        '4G_epc_wireless_active_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['single_remote_radio_unit'] == 4000 / setup_country_parameters['networks']['baseline_urban']

    setup_region[0]['sites_estimated_total'] = 6
    setup_region[0]['upgraded_sites'] = 3
    setup_region[0]['sites_3G'] = 3
    setup_region[0]['site_density'] = 2

    #test shared wholesale core network
    cost_structure = upgrade_to_4g(setup_region[0],
        '4G_epc_wireless_shared_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['regional_node'] == (
        (setup_costs['regional_node_epc'] * 2) /
        (setup_region[0]['sites_estimated_total'] / setup_country_parameters['networks']['baseline_urban'])
        / setup_country_parameters['networks']['baseline_urban'])


def test_greenfield_5g_nsa(setup_region, setup_option, setup_costs,
    setup_global_parameters, setup_core_lut, setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['new_sites'] = 1
    setup_region[0]['site_density'] = 1

    #test baseline infra sharing
    cost_structure = greenfield_5g_nsa(setup_region[0],
        '5G_nsa_wireless_baseline_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500
    assert cost_structure['single_remote_radio_unit'] == 4000
    assert cost_structure['tower'] == 10000
    assert cost_structure['civil_materials'] == 5000
    assert cost_structure['transportation'] == 5000
    assert cost_structure['installation'] == 5000
    assert cost_structure['site_rental'] == 9600
    assert cost_structure['power_generator_battery_system'] == 5000
    assert cost_structure['router'] == 2000

    #test passive infra sharing
    cost_structure = greenfield_5g_nsa(setup_region[0],
        '5G_nsa_wireless_passive_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['tower'] == 10000 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['civil_materials'] == 5000 / setup_country_parameters['networks']['baseline_urban']

    #test active infra sharing
    cost_structure = greenfield_5g_nsa(setup_region[0],
        '5G_nsa_wireless_active_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['single_remote_radio_unit'] == 4000 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['civil_materials'] == 5000 / setup_country_parameters['networks']['baseline_urban']

    setup_region[0]['sites_estimated_total'] = 6
    setup_region[0]['upgraded_sites'] = 3
    setup_region[0]['sites_3G'] = 3
    setup_region[0]['site_density'] = 2

    #test shared wholesale core network
    cost_structure = greenfield_5g_nsa(setup_region[0],
        '5G_nsa_wireless_shared_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['core_node'] == (
        (setup_costs['core_node_nsa'] * 2) /
        (setup_region[0]['sites_estimated_total'] / setup_country_parameters['networks']['baseline_urban'])
        ) / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['regional_node'] == (
        (setup_costs['regional_node_nsa'] * 2) /
        (setup_region[0]['sites_estimated_total'] / setup_country_parameters['networks']['baseline_urban'])
        / setup_country_parameters['networks']['baseline_urban'])


def test_upgrade_to_5g_nsa(setup_region, setup_option, setup_costs,
    setup_global_parameters, setup_core_lut, setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['upgraded_sites'] = 1
    setup_region[0]['sites_3G'] = 1
    setup_region[0]['site_density'] = 0.5

    cost_structure = upgrade_to_5g_nsa(setup_region[0],
        '5G_nsa_wireless_baseline_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500
    assert cost_structure['single_remote_radio_unit'] == 4000
    assert cost_structure['installation'] == 5000
    assert cost_structure['site_rental'] == 9600
    assert cost_structure['router'] == 2000

    #test passive infra sharing
    cost_structure = upgrade_to_5g_nsa(setup_region[0],
        '5G_nsa_wireless_passive_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['site_rental'] == 9600 / setup_country_parameters['networks']['baseline_urban']

    #test active infra sharing
    cost_structure = upgrade_to_5g_nsa(setup_region[0],
        '5G_nsa_wireless_active_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['single_sector_antenna'] == 1500 / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['single_remote_radio_unit'] == 4000 / setup_country_parameters['networks']['baseline_urban']

    setup_region[0]['sites_estimated_total'] = 6
    setup_region[0]['upgraded_sites'] = 3
    setup_region[0]['sites_3G'] = 3
    setup_region[0]['site_density'] = 2

    #test shared wholesale core network
    cost_structure = upgrade_to_5g_nsa(setup_region[0],
        '5G_nsa_wireless_shared_baseline_baseline_baseline',
        setup_costs, setup_global_parameters,
        setup_core_lut, setup_country_parameters)

    assert cost_structure['core_node'] == (
        (setup_costs['core_node_nsa'] * 2) /
        (setup_region[0]['sites_estimated_total'] /
        setup_country_parameters['networks']['baseline_urban'])
        ) / setup_country_parameters['networks']['baseline_urban']
    assert cost_structure['regional_node'] == (
        (setup_costs['regional_node_nsa'] * 2) /
        (setup_region[0]['sites_estimated_total'] /
        setup_country_parameters['networks']['baseline_urban'])
        / setup_country_parameters['networks']['baseline_urban'])


def test_get_backhaul_costs(setup_region, setup_costs, setup_core_lut):

    assert get_backhaul_costs(setup_region[0], 'wireless',
        setup_costs, setup_core_lut) == (setup_costs['wireless_small'])

    setup_region[0]['area_km2'] = 5000

    assert get_backhaul_costs(setup_region[0], 'wireless',
        setup_costs, setup_core_lut) == (setup_costs['wireless_small'])

    setup_region[0]['area_km2'] = 100000

    assert get_backhaul_costs(setup_region[0], 'wireless',
        setup_costs, setup_core_lut) == (setup_costs['wireless_large'])

    setup_region[0]['area_km2'] = 2

    assert get_backhaul_costs(setup_region[0], 'fiber',
        setup_costs, setup_core_lut) == (setup_costs['fiber_urban_m'] * 250)

    assert get_backhaul_costs(setup_region[0], 'incorrect_backhaul_tech_name',
        setup_costs, setup_core_lut) == 0


def test_regional_net_costs(setup_region, setup_option, setup_costs, setup_core_lut,
    setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 6

    assert regional_net_costs(setup_region[0], 'regional_edge', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (
            (setup_costs['regional_edge'] * setup_core_lut['regional_edge']['MWI.1.1.1_1_new']) /
            (setup_region[0]['sites_estimated_total'] /
            (setup_country_parameters['networks']['baseline_urban'])))

    assert regional_net_costs(setup_region[0], 'regional_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (
            (setup_costs['regional_node_epc'] * setup_core_lut['regional_node']['MWI.1.1.1_1_new']) /
            (setup_region[0]['sites_estimated_total'] /
            (setup_country_parameters['networks']['baseline_urban'])))

    setup_region[0]['sites_estimated_total'] = 10

    assert regional_net_costs(setup_region[0], 'regional_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (
            (setup_costs['regional_node_epc'] * setup_core_lut['regional_node']['MWI.1.1.1_1_new']) /
            (setup_region[0]['sites_estimated_total'] /
            (setup_country_parameters['networks']['baseline_urban'])))

    setup_core_lut['regional_node']['MWI.1.1.1_1'] = 10
    setup_region[0]['area_km2'] = 100

    assert regional_net_costs(setup_region[0], 'regional_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (
            (setup_costs['regional_node_epc'] * setup_core_lut['regional_node']['MWI.1.1.1_1_new']) /
            (setup_region[0]['sites_estimated_total'] /
            (setup_country_parameters['networks']['baseline_urban'])))

    assert regional_net_costs(setup_region[0], 'incorrrect_asset_name', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == 'Asset name not in lut'

    setup_region[0]['sites_estimated_total'] = 0

    assert regional_net_costs(setup_region[0], 'regional_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == 0

    setup_region[0]['GID_id'] = 'unknown GID ID'

    assert regional_net_costs(setup_region[0], 'regional_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == 0


def test_core_costs(setup_region, setup_option, setup_costs, setup_core_lut, setup_country_parameters):

    setup_region[0]['sites_estimated_total'] = 2
    setup_country_parameters['networks']['baseline_urban'] = 2

    assert core_costs(setup_region[0], 'core_edge', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (setup_costs['core_edge'] * 1000)

    assert core_costs(setup_region[0], 'core_node', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (setup_costs['core_node_{}'.format('epc')] * 2)

    assert core_costs(setup_region[0], 'incorrrect_asset_name', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == 0

    setup_region[0]['GID_id'] == 'unknown'

    assert core_costs(setup_region[0], 'core_edge', setup_costs,
        setup_core_lut, setup_option['strategy'], setup_country_parameters) == (
            (setup_costs['core_edge'] * setup_core_lut['core_edge']['MWI.1.1.1_1_new']) /
            (setup_region[0]['sites_estimated_total'] /
            (setup_country_parameters['networks']['baseline_urban'])))

    setup_core_lut['regional_node']['MWI.1.1.1_1'] = 3


def test_discount_capex_and_opex(setup_global_parameters, setup_country_parameters):

    assert discount_capex_and_opex(1000, setup_global_parameters, setup_country_parameters) == (
        1195 * (1 + (setup_country_parameters['financials']['wacc'] / 100)))


def test_discount_opex(setup_global_parameters, setup_country_parameters):

    assert discount_opex(1000, setup_global_parameters, setup_country_parameters) == (
        1952 * (1 + (setup_country_parameters['financials']['wacc'] / 100)))


def test_calc_costs(setup_region, setup_global_parameters, setup_country_parameters):

    setup_region[0]['sites_4G'] = 0
    setup_region[0]['upgraded_sites'] = 1
    setup_region[0]['new_sites'] = 1

    answer, structure = calc_costs(setup_region[0], {'single_sector_antenna': 1500}, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 5917

    answer, structure = calc_costs(setup_region[0], {'single_baseband_unit': 4000}, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 5259

    answer, structure = calc_costs(setup_region[0], {'tower': 10000}, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 11000

    answer, structure = calc_costs(setup_region[0], {'site_rental': 9600}, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 20617 #two years' of rent

    answer, structure = calc_costs(setup_region[0], {
        'single_sector_antenna': 1500,
        'single_baseband_unit': 4000,
        'tower': 10000,
        'site_rental': 9600
        }, 6, 'fiber', setup_global_parameters, setup_country_parameters)

    #answer = sum of antenna, bbu, tower, site_rental (5379 + 4781 + 10000 + 18743)
    assert answer == 42793

    answer, structure = calc_costs(setup_region[0], {'incorrect_name': 9600}, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 0 #two years' of rent

    answer, structure = calc_costs(setup_region[0], {
        'cots_processing': 6,
        'io_n2_n3': 6,
        'low_latency_switch': 6,
        'rack': 6,
        'cloud_power_supply_converter': 6,
        }, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 7

    answer, structure = calc_costs(setup_region[0], {
        'backhaul': 100,
    }, 1, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 132

    answer, structure = calc_costs(setup_region[0], {
        'backhaul': 100,
        }, 0, 'fiber', setup_global_parameters, setup_country_parameters)

    assert answer == 132


def test_find_single_network_cost(setup_region, setup_costs,
    setup_global_parameters, setup_country_parameters,
    setup_core_lut):

    #Test the UPGRADING of a single site to 4G
    #with wireless backhaul
    setup_region[0]['sites_4G'] = 0
    setup_region[0]['new_sites'] = 0
    setup_region[0]['upgraded_sites'] = 1 #single upgrade
    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['site_density'] = 0.5
    setup_region[0]['backhaul_new'] = 1 #single BH upgrade

    answer = find_single_network_cost(
        setup_region[0],
        {'strategy': '4G_epc_wireless_baseline_baseline_baseline_baseline'},
        setup_costs,
        setup_global_parameters,
        setup_country_parameters,
        setup_core_lut
    )

    assert round(answer['ran']) == 20273
    assert round(answer['backhaul_fronthaul']) == 26296
    assert round(answer['core_network']) == 0
    assert round(answer['network_cost']) == 72686

    #Test the UPGRADING of a single site to 5G NSA
    #with wireless backhaul
    setup_region[0]['sites_4G'] = 0
    setup_region[0]['new_sites'] = 0
    setup_region[0]['upgraded_sites'] = 1 #single upgrade
    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['site_density'] = 0.5
    setup_region[0]['backhaul_new'] = 1 #single BH upgrade

    answer = find_single_network_cost(
        setup_region[0],
        {'strategy': '5G_nsa_wireless_baseline_baseline_baseline_baseline'},
        setup_costs,
        setup_global_parameters,
        setup_country_parameters,
        setup_core_lut
    )

    assert round(answer['ran']) == 20273
    assert round(answer['backhaul_fronthaul']) == 26296
    assert round(answer['core_network']) == 140242
    assert round(answer['network_cost']) == 212928

    #Test the UPGRADING of a single site to 5G SA
    #with wireless backhaul
    setup_region[0]['sites_4G'] = 0
    setup_region[0]['new_sites'] = 0
    setup_region[0]['upgraded_sites'] = 1 #single upgrade
    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['site_density'] = 0.5
    setup_region[0]['backhaul_new'] = 1 #single BH upgrade

    answer = find_single_network_cost(
        setup_region[0],
        {'strategy': '4G_epc_wireless_baseline_baseline_baseline_baseline'},
        setup_costs,
        setup_global_parameters,
        setup_country_parameters,
        setup_core_lut
    )

    assert round(answer['ran']) == 20273
    assert round(answer['backhaul_fronthaul']) == 26296
    assert round(answer['core_network']) == 0
    assert round(answer['network_cost']) == 72686

    #Test the building of a single GREENFIELD 5G NSA site
    #with wireless backhaul
    setup_region[0]['sites_4G'] = 0
    setup_region[0]['new_sites'] = 1 #single new site
    setup_region[0]['upgraded_sites'] = 0
    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['site_density'] = 0.5
    setup_region[0]['backhaul_new'] = 1 #single new BH

    answer = find_single_network_cost(
        setup_region[0],
        {'strategy': '5G_nsa_wireless_baseline_baseline_baseline_baseline'},
        setup_costs,
        setup_global_parameters,
        setup_country_parameters,
        setup_core_lut
    )

    assert round(answer['ran']) == 20273
    assert round(answer['backhaul_fronthaul']) == 26296
    assert round(answer['core_network']) == 140242
    assert round(answer['network_cost']) == 241502

    #Test the building of a single GREENFIELD 5G SA site
    #with fiber backhaul
    setup_region[0]['sites_4G'] = 0
    setup_region[0]['new_sites'] = 1 #single new site
    setup_region[0]['upgraded_sites'] = 0
    setup_region[0]['sites_estimated_total'] = 1
    setup_region[0]['site_density'] = 0.5
    setup_region[0]['backhaul_new'] = 1 #single new BH
