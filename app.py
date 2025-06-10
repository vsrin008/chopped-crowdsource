import streamlit as st
import pandas as pd
import os
import random
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId

# MongoDB setup
client = MongoClient(st.secrets["mongodb_uri"])
db = client["face_rating_db"]
ratings_collection = db["ratings"]
users_collection = db["users"]

# Constants
IMAGE_FOLDER = "faces_to_rate"
PASSWORD = "choppedtheapp"

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
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            if login_password == PASSWORD and users_collection.find_one({"username": login_username}):
                st.session_state.user = login_username
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Choose a username", key="new_username")
        register_password = st.text_input("Enter password", type="password", key="register_password")
        
        if st.button("Register"):
            if register_password != PASSWORD:
                st.error("Invalid password")
            elif users_collection.find_one({"username": new_username}):
                st.error("Username already taken")
            elif new_username:
                users_collection.insert_one({"username": new_username})
                st.session_state.user = new_username
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Please enter a username")

# Rating interface
if st.session_state.authenticated:
    st.title(f"Rate This Face (1–5) - {st.session_state.user}")
    
    # Get images rated by this user
    user_rated_images = set(r["image"] for r in ratings_collection.find({"user": st.session_state.user}))
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
            ratings_collection.insert_one({
                "image": image_name,
                "rating": rating,
                "user": st.session_state.user,
                "timestamp": pd.Timestamp.now()
            })
            st.success("✅ Rating saved! Refresh to rate another.")
            
        # Show progress
        total_images = len(all_images)
        rated_count = len(user_rated_images)
        st.progress(rated_count / total_images)
        st.write(f"Progress: {rated_count}/{total_images} images rated")
