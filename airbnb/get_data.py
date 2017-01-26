"""
getting the data, unzipping it, and saving as a csv file
and also as a dump in a sql database
run from terminal
note: gunzip is a terminal command
"""

import os
import sys
import urllib.request
from subprocess import call
import glob
import pandas as pd

#sql stuff:
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import psycopg2


#local module:
sys.path.append("/Users/alexpapiu/Documents/Insight/airbnb_app/airbnb")
import airbnb_pipeline


os.chdir("/Users/alexpapiu/Documents/Insight/airbnb_app/Data")

links = ["http://data.insideairbnb.com/united-states/ny/new-york-city/2016-12-03/data/listings.csv.gz",
         "http://data.insideairbnb.com/united-states/ca/san-francisco/2016-07-02/data/listings.csv.gz",
         #"http://data.insideairbnb.com/united-states/ny/new-york-city/2015-01-01/data/listings.csv.gz"
         ]

#getting names for the filenames:
names = ["_".join(link.split("/")[-4:]) for link in links]

#unzipping the data:
for name, link in zip(names, links):
    urllib.request.urlretrieve(link, filename=name)

    #TODO:maybe do this in pyton directly?
    call(["gunzip", name])

#concatenate dataframes:
csv_names = [name.replace(".gz", "") for name in names]
data = pd.concat([pd.read_csv(file) for file in csv_names])

data = data.set_index("id")
#fast removal of duplicate listings:
dedup_data = data[~data.index.duplicated(keep='first')]
#save the data to a new csv_file:
dedup_data.to_csv("dedup_listings.csv")


#~~~~~~~~~~~~~~~~~~~~~~
#dumping to a Postgres database:
#~~~~~~~~~~~~~~~~~~~~~~~

dedup_data = pd.read_csv("dedup_listings.csv", index_col = "id")
clean_data = airbnb_pipeline.small_clean(dedup_data)


location_descriptions = dedup_data[["neighborhood_overview", "neighbourhood_cleansed", "city", "latitude", "longitude"]]
location_descriptions = location_descriptions.dropna()

dbname = 'airbnb_db'
username = 'alexpapiu'

con = psycopg2.connect(database = dbname, user = username)


engine = create_engine('postgres://%s@localhost/%s'%(username,dbname))
#print(engine.url)

#if not database_exists(engine.url):
#    create_database(engine.url)
#print(database_exists(engine.url))

#small_listings for kde, location_descp for lda and neighborhood recommendations:
clean_data.to_sql('small_listings', engine, if_exists='replace', index=True)
location_descriptions.to_sql('location_descriptions', engine, if_exists = 'replace', index = True)

#mock listings for testing:
clean_data[:10].to_sql('mock_listings', engine, if_exists='replace', index=True)
clean_data[:10].to_csv('mock_clean_data.csv', )



#~~~~~~~~~~~~~~~~~~~~~
#getting the images:
#~~~~~~~~~~~~~~~~~~~~~

os.chdir("/Users/alexpapiu/Documents/Insight/Project/Data/Thumbnails")
images_url = dedup_data.thumbnail_url

#save them as listings_id.jpg
listings_id = pd.Series(images_url.index).str.split("/", expand = True)[4]

#this takes like 5 imgs/second:
for i in range(1000):
    try:
        urllib.request.urlretrieve(images_url[i], listings_id[i]+ ".jpg")
    except:
        pass