import arcpy
import os
import arcpy.na
import pandas as pd
from datetime import date

# Check out Network Analyst license if available. Fail if the Network Analyst license is not available.
if arcpy.CheckExtension("network") == "Available":
    arcpy.CheckOutExtension("network")
else:
    raise arcpy.ExecuteError("Network Analyst Extension license is not available.")

# Manually download the Accela inspection data report (I named it 'routecsv.csv')

# Read in the csv file
routeData = pd.read_csv(r"csv file path")

# Create a dictionary of the inspectors
inspector_dict = routeData.to_dict(orient='list')

# Set environment to InspectionRouting.gdb
arcpy.env.workspace = r"Insert GIS workspace path"
arcpy.env.overwriteOutput = True  # Set to true so "TodaysInspection" will always be overwritten
# insert code to delete all files in Inspectors dataset (use if: to exclude 'CurrentParcels')
# to be added

# This creates a copy of the parcel layer from the SDE into the current workspace
parcel_layer = r"parcel layer path"
parcel_out_feature = "CurrentParcels"

arcpy.management.CopyFeatures(parcel_layer, parcel_out_feature)

# Initialize variables
in_feature = "CurrentParcels"  # initialize the in feature for arcpy later
whereclause = []  # initialize empty where clause list
network_dataset = r"road network file path"
today = date.today()
today = today.strftime("%m%d")

# Select the parcels needed for each inspectors route
for inspector in inspector_dict.keys():
    for stop in inspector_dict[inspector]:
        if str(stop) == 'nan':
            break
        whereclause.append("Assesor_NO = " + "'" + str(stop) + "' " + "OR")
    whereclause = (' '.join(whereclause))  # combines the list of where clauses into a single clause
    whereclause = whereclause[:-3]  # removes the 'OR' from final stop
    print(whereclause)  # so you can check the list as it is being processed
    out_feature = f"{inspector}Parcels"
    arcpy.Select_analysis(in_feature, out_feature, whereclause)  # create parcels
    # Now we convert the parcel polygons to points so we can make a route
    point_in = out_feature
    point_out = f"{inspector}RoutePoints"
    arcpy.management.FeatureToPoint(point_in, point_out, "CENTROID")  # create points from polygons
    whereclause = []  # reset the where clause for next inspector

    # Add new 'sequence' field to the inspectorRoutePoints(point_out) layer
    arcpy.management.AddField(point_out, 'Sequence', 'DOUBLE')

    # create route layer for the current inspector
    route_name = f"{inspector}Route{today}"  # give name to route layer
    inspector_route_object = arcpy.na.MakeRouteAnalysisLayer(network_dataset, route_name, sequence='PRESERVE_BOTH')
    # create route analysis layer, which preserves first and last stop in sequence
    inspector_route_layer = inspector_route_object.getOutput(0)
    sublayer_names = arcpy.na.GetNAClassNames(inspector_route_layer)  # Get sublayer names within route layer
    stops_layer_name = sublayer_names["Stops"]  # store the stops sublayer
    barriers_layer_name = sublayer_names["PolylineBarriers"]
    arcpy.na.AddLocations(inspector_route_layer, barriers_layer_name,
                          r"barriers layer if applicable(ie. long-term road closures to take into account")  # import road barriers

    # create field mappings to properly set sequencing for the stops
    field_mappings = arcpy.na.NAClassFieldMappings(inspector_route_layer, stops_layer_name)
    field_mappings["Sequence"].mappedFieldName = "Sequence"
    field_mappings["Sequence"].defaultValue = "2"

    # import the stops to the route layer, office stops and route stops
    arcpy.na.AddLocations(inspector_route_layer, stops_layer_name, point_out, field_mappings)
    arcpy.na.AddLocations(inspector_route_layer, stops_layer_name,
                          r"point layer that contains office location", field_mappings)

    # solve the route
    arcpy.na.Solve(inspector_route_layer, "SKIP")

    # share the route layer to AGOL
    arcpy.na.ShareAsRouteLayers(inspector_route_layer, route_name_prefix = f'{inspector}{today}',
                                portal_folder_name='folder name', share_with='MYORGANIZATION')

    # OR share route layer to local disk (Not using as of now)
    # save_space = r"save space path"
    # output_layer_file = os.path.join(save_space, route_name + ".lyrx" )
    # inspector_route_layer.saveACopy(output_layer_file)

    print(f"{inspector.title()}'s route for {today} has been created.")
