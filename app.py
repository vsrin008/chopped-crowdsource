import streamlit as st
import pandas as pd
import os
import random
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi
import requests
import time
from datetime import datetime
import json

# MongoDB setup
try:
    # Get MongoDB URI from secrets
    mongodb_uri = st.secrets["mongodb_uri"]
    
    # Configure client with proper SSL settings
    client = MongoClient(
        mongodb_uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        maxPoolSize=50,
        retryWrites=True,
        w='majority'
    )
    
    # Test the connection
    client.admin.command('ping')
    db = client['face_ratings']
    ratings_collection = db['ratings']
    st.session_state['db_connected'] = True
    
except Exception as e:
    st.error(f"MongoDB Connection Error: {str(e)}")
    st.session_state['db_connected'] = False
    # Fallback to CSV if MongoDB fails
    if 'ratings' not in st.session_state:
        st.session_state['ratings'] = []

# Constants
IMAGE_FOLDER = "faces_to_rate"
PASSWORD = "choppedtheapp"

def save_rating(image_name, rating):
    try:
        if st.session_state['db_connected']:
            # Create a new document for each rating
            ratings_collection.insert_one({
                "user": st.session_state.user,
                "image": image_name,
                "rating": rating,
                "timestamp": datetime.now()
            })
        else:
            # Update in-memory ratings
            for r in st.session_state.ratings:
                if r["image"] == image_name:
                    r["rating"] = rating
                    return
            st.session_state.ratings.append({
                "image": image_name,
                "rating": rating,
                "timestamp": datetime.now()
            })
    except Exception as e:
        st.error(f"Error saving rating: {str(e)}")

# Initialize session state
if 'user' not in st.session_state:
    st.session_state.user = ""
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Get all images
all_images = os.listdir(IMAGE_FOLDER)

# Authentication interface
if not st.session_state.authenticated:
    st.title("Welcome to Face Rating!")
    
    # Debug information
    if st.session_state.db_connected:
        st.success("✅ Connected to MongoDB")
        user_count = ratings_collection.count_documents({})
        st.write(f"Total ratings in database: {user_count}")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            try:
                user = ratings_collection.find_one({"user": login_username})
                if login_password == PASSWORD and user:
                    st.session_state.user = login_username
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            except Exception as e:
                st.error(f"Login Error: {str(e)}")
    
    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Choose a username", key="new_username")
        register_password = st.text_input("Enter password", type="password", key="register_password")
        
        if st.button("Register"):
            try:
                if register_password != PASSWORD:
                    st.error("Invalid password")
                elif ratings_collection.find_one({"user": new_username}):
                    st.error("Username already taken")
                elif new_username:
                    ratings_collection.insert_one({"user": new_username})
                    st.session_state.user = new_username
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Please enter a username")
            except Exception as e:
                st.error(f"Registration Error: {str(e)}")

# Rating interface
if st.session_state.authenticated:
    st.title(f"Rate This Face (1–5) - {st.session_state.user}")
    
    # Get images rated by this user
    try:
        # First check if user exists and has any ratings
        user_doc = ratings_collection.find_one({"user": st.session_state.user})
        if not user_doc:
            # If user doesn't exist, create their document
            ratings_collection.insert_one({"user": st.session_state.user, "ratings": []})
            user_rated_images = set()
        else:
            # Get all images rated by this user
            user_ratings = list(ratings_collection.find(
                {"user": st.session_state.user, "image": {"$exists": True}}
            ))
            user_rated_images = set(r["image"] for r in user_ratings)

        unrated_images = list(set(all_images) - user_rated_images)

        if not unrated_images:
            st.success(f"🎉 You have rated all {len(all_images)} images!")
            if st.button("Logout"):
                st.session_state.user = ""
                st.session_state.authenticated = False
                st.rerun()
        else:
            image_name = random.choice(unrated_images)
            image_path = os.path.join(IMAGE_FOLDER, image_name)

            st.image(Image.open(image_path), caption=image_name, use_column_width=True)
            
            # Create 5 buttons in a row
            col1, col2, col3, col4, col5 = st.columns(5)
            rating = None
            
            with col1:
                if st.button("1", use_container_width=True):
                    rating = 1
            with col2:
                if st.button("2", use_container_width=True):
                    rating = 2
            with col3:
                if st.button("3", use_container_width=True):
                    rating = 3
            with col4:
                if st.button("4", use_container_width=True):
                    rating = 4
            with col5:
                if st.button("5", use_container_width=True):
                    rating = 5
                    
            if rating is not None:
                try:
                    save_rating(image_name, rating)
                    st.success("✅ Rating saved! Refresh to rate another.")
                except Exception as e:
                    st.error(f"Error saving rating: {str(e)}")
                
            # Show progress
            total_images = len(all_images)
            rated_count = len(user_rated_images)
            st.progress(rated_count / total_images)
            st.write(f"Progress: {rated_count}/{total_images} images rated")
    except Exception as e:
        st.error(f"Error loading ratings: {str(e)}")
        if st.button("Logout"):
            st.session_state.user = ""
            st.session_state.authenticated = False
            st.rerun()

def load_ratings():
    try:
        if st.session_state['db_connected']:
            # Get all ratings for the current user
            user_ratings = list(ratings_collection.find(
                {"user": st.session_state.user},
                {"_id": 0, "user": 0}  # Exclude _id and user fields
            ))
            return user_ratings
        else:
            return st.session_state.ratings
    except Exception as e:
        st.error(f"Error loading ratings: {str(e)}")
        return []

def display_ratings():
    st.subheader("Your Ratings")
    try:
        if st.session_state['db_connected']:
            # Get all ratings for the current user
            user_ratings = list(ratings_collection.find(
                {"user": st.session_state.user}
            ).sort("timestamp", -1))
            
            if not user_ratings:
                st.write("No ratings yet. Start rating faces!")
                return
                
            # Create a DataFrame for display
            ratings_df = pd.DataFrame(user_ratings)
            ratings_df['timestamp'] = pd.to_datetime(ratings_df['timestamp'])
            ratings_df = ratings_df[['image', 'rating', 'timestamp']]
            ratings_df.columns = ['Image', 'Rating', 'Time']
            st.dataframe(ratings_df)
        else:
            if not st.session_state.ratings:
                st.write("No ratings yet. Start rating faces!")
                return
                
            # Create a DataFrame for display
            ratings_df = pd.DataFrame(st.session_state.ratings)
            ratings_df['timestamp'] = pd.to_datetime(ratings_df['timestamp'])
            ratings_df = ratings_df[['image', 'rating', 'timestamp']]
            ratings_df.columns = ['Image', 'Rating', 'Time']
            st.dataframe(ratings_df)
    except Exception as e:
        st.error(f"Error displaying ratings: {str(e)}")
