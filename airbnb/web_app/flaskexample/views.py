import os
import sys
import pandas as pd
import numpy as np
import folium

from sklearn.externals import joblib
from sklearn.neighbors import NearestNeighbors

from flask import render_template
from flask import request

#local module:
from flaskexample import app
from flaskexample import airbnb_pipeline



import psycopg2
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database

from bokeh.charts import Histogram
from bokeh.embed import components


home_folder = os.environ["home_folder"]
dbname = os.environ["dbname"]
username = os.environ["username"]

if sys.platform == "linux":
    password = os.environ["password"]

if sys.platform == "linux":
    connect_str = "dbname='%s' user='%s' host='localhost' password='%s'"%(dbname,username,password)
    con = psycopg2.connect(connect_str)
else:
    con = psycopg2.connect(database = dbname, user = username)



train = pd.read_sql_query("SELECT * FROM location_descriptions", con)
train["id"] = train["id"].astype("float").astype("int")


listings = pd.read_sql_query(
            """
            SELECT id, price, diff, neighbourhood_cleansed,listing_url,
            name, summary, preds, medium_url, city, room_type FROM listings_price
            """, con)

train = train.merge(listings)

#visualaizing preds.
# %matplotlib inline
# import seaborn as sns
# #doing the ratio thing:
# temp = train[train["room_type"] == "Private room"][train["price"] < 200][["preds", "price"]]
# #%config InlineBackend.figure_format = 'retina'
#
#
# temp["ratio"] = (temp["preds"] - temp["price"])/temp["price"]
# temp["good"] = 0
# temp["good"][temp["ratio"] < 0] = 1
# temp["good"][temp["ratio"] > 0][temp["ratio"] < 0.6] = 2
# temp.loc[(temp["ratio"] > 0) & (temp["ratio"] < 0.6), "good"] = 2
# sns.lmplot(x = "price", y = "preds", data = temp, hue = "good", fit_reg = False, palette = "Dark2")


nbd_counts = train["neighbourhood_cleansed"].value_counts()
descp = train[["id", "neighborhood_overview"]]
descp = descp.drop_duplicates()

nbds = list(nbd_counts[:40].index)


print("loading models")
model = joblib.load(os.path.join(home_folder, 'airbnb_app/Data/tf_idf_model.pkl'))

knn = NearestNeighbors(500, metric = "cosine", algorithm = "brute")
X = descp["neighborhood_overview"]

#somewhat slow - could save the projections first here:
X_proj = model.transform(X)

#fast since there's no real fittting going on here
#should check how fast predicting is - should be fine for a few values.
knn.fit(X_proj)


#for debugging:
# descp = "hip trendy cool"
# descp_2 = "gritty urban"
# descp_3 = "dangerous"
# map_osm = get_heat_map(str(descp), knn, model, train)
# map_osm = add_heat_layer(map_osm, descp_2,knn, model, train, scale=scale_2)
# map_osm = add_heat_layer(map_osm, descp_3,knn, model, train, scale  = scale_3)
# folium.LayerControl().add_to(map_osm)
# map_osm.save(outfile='map_test.html')

#~~~~~~~~~~
#Map Views:
#~~~~~~~~~~

@app.route('/')
@app.route('/home')
def map_input():
    return render_template("home.html", nbds = nbds)


@app.route('/map')
def return_map():
        descp = request.args.get('descp')

        descp_2 = None
        descp_3 = None

        try:
            descp_2 = request.args.get('map_descp_2')
            descp_3 = request.args.get('map_descp_3')
        except:
            pass

        map_osm = airbnb_pipeline.get_heat_map(str(descp), knn, model, train)

        if descp_2 and descp_2 is not "":
            map_osm = airbnb_pipeline.add_heat_layer(map_osm, descp_2,knn,
                                                     model, train, scale  = 1)

        if descp_2 and descp_3 is not "":
            map_osm = airbnb_pipeline.add_heat_layer(map_osm, descp_3,knn,
                                                     model, train, scale  = 2)

        folium.LayerControl().add_to(map_osm)

        #TODO: find a way to add custom html on top of map
        #maybe add the nbd scores over it.

        #TODO:make this serve the map directly?
        #this will save the map and then reload it
        #sounds like it could be slow but it's actually very fast.
        map_osm.save(outfile='flaskexample/templates/map.html')

        return render_template("map.html")
        #return render_template("rec_temp.html")

#~~~~~~~~~~~~~~~~~~~
#Neighborhood Views:
#~~~~~~~~~~~~~~~~~~~

@app.route('/nbd')
def nbd():
    #pull 'nbd' from input field and store it:
    nbd = request.args.get('nbd')
    room_type = "Private room"


    #nbd = "East Village"

    train = pd.read_sql_query("""
                           SELECT * FROM listings_price
                           WHERE neighbourhood_cleansed = %(nbd)s
                           AND room_type = %(room_type)s;
                           """,
                           con, index_col = "id",
                           params = {"nbd":nbd, "room_type":room_type})


    #train

    train["ratio"] = (train["preds"] - train["price"])/train["price"]




    #keep train for the histogram
    sm_train = train[train["ratio"] > 0][train["ratio"] < 1.2]
    sm_train = sm_train.sort_values("diff", ascending = False)


    sm_train["diff"]
    births = []


    #showing some tables:
    for i in range(0,25):
       births.append(dict(price=int(sm_train.iloc[i]['price']),
                          city=sm_train.iloc[i]['name'],
                          id = sm_train.index[i],
                          room_type=int(sm_train.iloc[i]['preds']),
                          url=sm_train.iloc[i]['listing_url']))
       the_result = ''


    #births
    plot = Histogram(train["price"], bins = 20, plot_width=500, plot_height=300)
    script, div = components(plot)
    title = "Distribution of daily prices in {0}".format(nbd)

    median = train["price"].median()
    percentile_05 = np.round(train["price"].quantile(0.05), 1)
    percentile_95 = np.round(train["price"].quantile(0.95), 1)

    more_info = "The median price per day is ${0}. 95% of the listings are in \
                 between ${1} and ${2}".format(median, percentile_05, percentile_95)

    return render_template('nbd.html', births = births, the_result = the_result, nbd = nbd,
                           script = script, div = div, title = title, more_info = more_info)


@app.route('/nbd_rec')
def nbd_rec():
    descp = request.args.get('descp')


    #map:
    map_osm = airbnb_pipeline.get_heat_map(str(descp), knn, model, train)
    map_osm.save(outfile='flaskexample/templates/map.html')

    #scores:
    nbd_score = airbnb_pipeline.get_nbds(descp, knn = knn,
                                model = model, train = train, nbd_counts = nbd_counts)


    nbd_score = (nbd_score["weighted_score"].replace(np.inf, np.nan).dropna().
                sort_values(ascending = False).head(10))

    nbd_score = np.sqrt(np.sqrt(np.sqrt(nbd_score/np.max(nbd_score))))*95



    nbd_score_list = []
    for i in range(10):
        nbd_score_list.append(dict(name = nbd_score.index[i], score = int(nbd_score.iloc[i])))

    return render_template('nbd_rec.html', nbds = nbd_score_list, descp = descp)


@app.route('/listing')
def listing():

    listing_id = int(request.args.get('listing_id'))
    #listing_id = 685006
    #one_listing = listings.iloc[0]


    one_listing = listings[listings["id"] == listing_id].iloc[0]



    title = one_listing["name"]
    summary = one_listing["summary"]
    text = ("The predicted daily price for this listing is {0}$ which is {1}$ from the actual price {2}$"
                      .format(int(one_listing.preds),
                              int(one_listing["diff"]),
                              int(one_listing.price)))
    photo_link = one_listing["medium_url"]

    plot = airbnb_pipeline.get_price_plot(one_listing = one_listing, std = 35)
    script, div = components(plot)

    return render_template('listing_view.html', script = script, div = div, summary = summary,
                           text = text, link = one_listing.listing_url, title = title, photo_link = photo_link)



@app.route('/description')
def description():
    return render_template('description_2.html')



@app.route('/about_me')
def about_me():
    return render_template('about_me.html')
