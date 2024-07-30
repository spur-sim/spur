#this script converts GTFS input to spur input
#input routes.txt, stop_times.txt, stops.txt, trips.txt
#output components.json, routes.json, tours.json
#trains.json is not generated as there is no corresponding file in GTFS
#yards are not generated and to be added by the user
#code assumes double track operations - if a trip goes from A to B and another trip goes from B to A, then one track is assigned key 1 and the other one is assigned key 2 

import pandas as pd
import copy
import json
from datetime import datetime
import csv
from collections import defaultdict
import os
import numpy as np
stations={}
edges={}
routes={}
tours={}
counter=1


#this part only keeps routes that are type 1 or 2 which correspond to rail
df_routes = pd.read_csv('routes.txt', sep=',')
df_routes.drop(df_routes[~df_routes['route_type'].isin([1, 2])].index, inplace=True)

df_trips=pd.read_csv("trips.txt", delimiter=",")
df_trips = df_trips[df_trips['route_id'].isin(df_routes['route_id'])]
df_stoptimes=pd.read_csv("stop_times.txt", delimiter=",")
df_stoptimes = df_stoptimes[df_stoptimes['trip_id'].isin(df_trips['trip_id'])]
df_stoptimes.sort_values(by=['trip_id', 'stop_sequence'], inplace=True)

#this section replaces the values under stop_id with their corresponding stop_name values
df_stops=pd.read_csv("stops.txt", delimiter=",")
stop_id_to_name = df_stops.set_index('stop_id')['stop_name'].to_dict()
df_stoptimes['StationName'] = df_stoptimes['stop_id'].map(stop_id_to_name)
df_stoptimes['stop_id'] = df_stoptimes['StationName']

#get the ordered list of stops per trip
list_trip_ids = df_stoptimes["trip_id"].unique().tolist()
ordered_list_of_trips=[]
ordered_list_of_stations=[]
for trip_id in list_trip_ids: #here we get the list of stations in order per trip
    temp_df=df_stoptimes.loc[df_stoptimes["trip_id"] == trip_id]
    temp_df=temp_df.sort_values(by="stop_sequence", ascending=True)
    list_stations_per_trip=temp_df["stop_id"].tolist()
    ordered_list_of_stations.append(list_stations_per_trip)
    ordered_list_of_trips.append(temp_df["trip_id"].tolist()[0])

#identify identical trips (stop_time sequences)
identical_trip_groups = []
seen_sequences = {}
duplicate_station_sequence=[]

for i, sta in enumerate(ordered_list_of_stations):
    station_sequence = tuple(sta)
    if station_sequence in seen_sequences:
        identical_trip_groups[seen_sequences[station_sequence]].append(ordered_list_of_trips[i])
        duplicate_station_sequence.append(sta)
    else:
        seen_sequences[station_sequence] = len(identical_trip_groups)
        identical_trip_groups.append([ordered_list_of_trips[i]])

#this part gets the average travel times between station pairs
df_stoptimes.to_csv('modified_stop_times.txt', sep=',', index=False) #temp file
with open("modified_stop_times.txt", "r") as file:
    reader = csv.DictReader(file)
    travel_times = defaultdict(list)
    prev_stop = {}
    for row in reader:
        trip_id = row['trip_id']
        stop_id = row['stop_id']
        sequence = int(row['stop_sequence'])
        arrival_time = row['arrival_time']
    
        if prev_stop!={}:
            if sequence > 1 and prev_stop['trip_id'] == trip_id:
                pair = (prev_stop['stop_id'], stop_id)
                hours, minutes, seconds = map(int, arrival_time.split(':'))    
                arrival_time_in_seconds = hours * 3600 + minutes * 60 + seconds
                hours, minutes, seconds = map(int, prev_stop['departure_time'].split(':'))    
                departure_time_in_seconds = hours * 3600 + minutes * 60 + seconds
                travel_time=arrival_time_in_seconds-departure_time_in_seconds
                travel_times[pair].append(travel_time)
    
        prev_stop = {
            'trip_id': trip_id,
            'stop_id': stop_id,
            'departure_time': row['departure_time'],
            'sequence': sequence
        }
    average_travel_times = [[pair[0], pair[1], sum(times)/len(times)] for pair, times in travel_times.items()]
    file.close()
    os.remove('modified_stop_times.txt')

#here the dictionaries of stations and edges are created 
routes_list=[]
processed_list_of_stations=[]
compiled_list_of_routes=[]
for list_of_stations in ordered_list_of_stations: #here we create the database of stations
    if list_of_stations in processed_list_of_stations: #if the path has already been processed
        routes_list=[]
        continue
    elif list_of_stations[::-1] in processed_list_of_stations: #if the reverse of this path has been processed, a second track is added 
        for index, station in enumerate(list_of_stations):
            stations['Station'+str(counter)]={'type':'SimpleStation','name':str(station)+"_2",'u':str(station)+"_1",'v':str(station)+"_2",'key':2,'args':{'mean_boarding': 20,'mean_alighting': 20}}
            routes_list.append(['u:'+str(station)+"_2",'v:'+str(station)+"_1",'key:'+"2"])
            if index==0:
                pass
            else:
                previous_station=list_of_stations[index-1]
                for travel_time in average_travel_times:
                    if travel_time[0]==previous_station and travel_time[1]==station:
                        average_travel_time=travel_time[2]
                        break
                edges['Edge'+str(counter)]={'type':'TimedTrack','u':str(previous_station)+"_2",'v':str(station)+"_1",'key':2,"traversal_time": average_travel_time}
                routes_list.insert(-1,['u:'+str(previous_station)+"_1",'v:'+str(station)+"_2",'key:'+"2"])
            counter=counter+1
        compiled_list_of_routes.append(routes_list)
        routes_list=[]
        continue    
    else:
        for index, station in enumerate(list_of_stations): #base case, the path hasnt been processed yet
            stations['Station'+str(counter)]={'type':'SimpleStation','name':str(station)+"_1",'u':str(station)+"_1",'v':str(station)+"_2",'key':1,'args':{'mean_boarding': 20,'mean_alighting': 20}}
            routes_list.append(['u:'+str(station)+"_1",'v:'+str(station)+"_2",'key:'+"1"])
            if index==0:
                pass
            else:
                previous_station=list_of_stations[index-1]
                for travel_time in average_travel_times:
                    if travel_time[0]==previous_station and travel_time[1]==station:
                        average_travel_time=travel_time[2]
                        break
                edges['Edge'+str(counter)]={'type':'TimedTrack','u':str(previous_station)+"_2",'v':str(station)+"_1",'key':1,"traversal_time": average_travel_time}
                routes_list.insert(-1,['u:'+str(previous_station)+"_2",'v:'+str(station)+"_1",'key:'+"1"])
            counter=counter+1
    processed_list_of_stations.append(list_of_stations)
    compiled_list_of_routes.append(routes_list)
    routes_list=[]

#here we remove duplicate station entries
unique_combinations = {}
for station_key, station_info in stations.items():
    key_tuple = (station_info['u'], station_info['v'], station_info['key'])
    unique_combinations[key_tuple] = station_info
stations_clean = {f'Station{i}': info for i, (_, info) in enumerate(unique_combinations.items(), start=1)}

#here we remove duplicate edge entries
unique_combinations = {}
for edge_key, edge_info in edges.items():
    key_tuple = (edge_info['u'], edge_info['v'], edge_info['key'])
    unique_combinations[key_tuple] = edge_info
edges_clean = {f'Edge{i}': info for i, (_, info) in enumerate(unique_combinations.items(), start=1)}


for i, route in enumerate(compiled_list_of_routes, start=0): #since routes was stored as a list, it's converted to dict here
    route_key=ordered_list_of_trips[i]
    routes[route_key]={}
    for j, component in enumerate(route, start=1):
        comp_key = f'component{j}'
        u, v, key =component
        routes[route_key][comp_key]={'u': u.split(':')[1], 'v': v.split(':')[1], 'key': int(key.split(':')[1])}


#merge trips and stop_times to tie trips and blocks to departure times
df_stoptimes = df_stoptimes.merge(df_trips[['trip_id', 'block_id']], on='trip_id', how='left')
df_dict = df_stoptimes.to_dict('records')

for record in df_dict: #loop to create a dict called tours which contains the trips and their departure times 
    block_id = 'block' + str(record['block_id'])
    trip_id = record['trip_id']
    departure_time = {'departure': record['departure_time']}
    if block_id not in tours:
        tours[block_id] = {}
    if trip_id not in tours[block_id]:
        tours[block_id][trip_id] = []
    tours[block_id][trip_id].append(departure_time)

# This function converts time to seconds since midnight (useful in tours.json since departure times are seconds away from 0
def time_to_seconds(t):
    h, m, s = map(int, t.split(':'))
    return h * 3600 + m * 60 + s

formatted_tours = []

for block, trips in tours.items():
    block_id = block.replace('block', '')
    block_dict = {
        "name": block_id,
        "creation_time": 0,
        "deletion_time": 172800,
        "routes": []
    }
    
    for trip, times in trips.items():
        args_list = []
        for time in times:
            args_list.append({"departure": time_to_seconds(time['departure'])})
            args_list.append(None)  # Insert None between departures (since stations have departure times but tracks do not, and in GTFS, only stations are represented, so it's safe to add null between the departure times)
        args_list.pop()  # Remove the last None to avoid having it after the last departure
        for identical_trip_group in identical_trip_groups: #this condition checks if a trip is identical to another trip, then the first instance of the trip_id will be used for all the identical trips
            if len(identical_trip_group)>1:
                if trip in identical_trip_group[1:]:
                    route_dict = {
                        "name": identical_trip_group[0],
                        "args": args_list
                    }
                    break
                else:
                    route_dict = {
                        "name": trip,
                        "args": args_list
                    }
        block_dict["routes"].append(route_dict)
    
    formatted_tours.append(block_dict)

tours_json = json.dumps(formatted_tours, indent=2)
with open('tours.json', 'w') as file:
    json.dump(formatted_tours, file, indent=2)

#create components data
formatted_stations=list(stations_clean.values()) 
formatted_edges = list(edges_clean.values())
combined_data = formatted_stations + formatted_edges

# Save the combined component data to a JSON file
with open('components.json', 'w') as json_file:
    json.dump(combined_data, json_file, indent=4)

formatted_routes = []
for trip_name, components in routes.items():
    formatted_components = [details for key, details in components.items()]
    formatted_routes.append({
        "name": trip_name,
        "components": formatted_components
    })

with open('routes.json', 'w') as json_file:
    json.dump(formatted_routes, json_file, indent=2)

