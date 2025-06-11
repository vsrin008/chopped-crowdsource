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
    mongodb_uri = st.secrets["mongodb_uri"]
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
    client.admin.command('ping')
    db = client['face_ratings']
    ratings_collection = db['ratings']
    st.session_state['db_connected'] = True
except Exception as e:
    st.error(f"MongoDB Connection Error: {str(e)}")
    st.session_state['db_connected'] = False
    if 'ratings' not in st.session_state:
        st.session_state['ratings'] = []

# Constants
IMAGE_FOLDER = "faces_to_rate"
PASSWORD = "choppedtheapp"

# Global styles
st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem !important;
    }

    .image-container {
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        background-color: #f7f7f7;
        padding: 10px;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.05);
        display: flex;
        justify-content: center;
    }

    button[kind="secondary"]:hover {
        opacity: 0.9;
        transition: 0.2s ease-in-out;
    }

    h1 {
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

def save_rating(image_name, rating):
    try:
        if st.session_state['db_connected']:
            # Check if this image has already been rated by this user
            existing_rating = ratings_collection.find_one({
                "user": st.session_state.user,
                "image": image_name
            })
            
            if existing_rating:
                # Update existing rating
                ratings_collection.update_one(
                    {"user": st.session_state.user, "image": image_name},
                    {"$set": {"rating": rating, "timestamp": datetime.now()}}
                )
            else:
                # Create new rating
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
                    r["timestamp"] = datetime.now()
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
if 'current_image' not in st.session_state:
    st.session_state.current_image = None

# Get all images
all_images = os.listdir(IMAGE_FOLDER)

# Authentication interface
if not st.session_state.authenticated:
    st.title("Welcome to Face Rating!")
    
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
    st.title(f"Rate This Face (1–10) - {st.session_state.user}")
    
    try:
        # Get images rated by this user
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
            # Select a new image if we don't have one or if we're skipping
            if st.session_state.current_image is None or st.session_state.current_image in user_rated_images:
                st.session_state.current_image = random.choice(unrated_images)
            
            image_name = st.session_state.current_image
            image_path = os.path.join(IMAGE_FOLDER, image_name)

            left, center, right = st.columns([1, 2, 1])
            with center:
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(Image.open(image_path), caption=image_name, width=250)
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("### Rate this face:")
            col1, col2, col3, col4, col5 = st.columns(5)
            col6, col7, col8, col9, col10 = st.columns(5)
            rating = None

            with col1:
                if st.button("1", use_container_width=True): rating = 1
            with col2:
                if st.button("2", use_container_width=True): rating = 2
            with col3:
                if st.button("3", use_container_width=True): rating = 3
            with col4:
                if st.button("4", use_container_width=True): rating = 4
            with col5:
                if st.button("5", use_container_width=True): rating = 5
            with col6:
                if st.button("6", use_container_width=True): rating = 6
            with col7:
                if st.button("7", use_container_width=True): rating = 7
            with col8:
                if st.button("8", use_container_width=True): rating = 8
            with col9:
                if st.button("9", use_container_width=True): rating = 9
            with col10:
                if st.button("10", use_container_width=True): rating = 10

            st.markdown("---")
            if st.button("⏭️ Skip this image for now", use_container_width=True):
                st.session_state.current_image = None
                st.success("Image skipped! Refresh to see another image.")
                st.rerun()

            if rating is not None:
                try:
                    save_rating(image_name, rating)
                    st.session_state.current_image = None  # Clear current image after rating
                    st.success("✅ Rating saved! Refresh to rate another.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving rating: {str(e)}")

            st.markdown("### Progress")
            total_images = len(all_images)
            rated_count = len(user_rated_images)
            progress = rated_count / total_images

            st.markdown(f"""
                <style>
                .progress-container {{
                    background-color: #f0f0f0;
                    border-radius: 10px;
                    padding: 3px;
                    margin: 10px 0;
                }}
                .progress-bar {{
                    background-color: #4CAF50;
                    height: 20px;
                    border-radius: 8px;
                    width: {progress * 100}%;
                    transition: width 0.3s ease;
                }}
                </style>
                <div class="progress-container">
                    <div class="progress-bar"></div>
                </div>
            """, unsafe_allow_html=True)

            st.write(f"📊 {rated_count}/{total_images} images rated ({int(progress * 100)}%)")

    except Exception as e:
        st.error(f"Error loading ratings: {str(e)}")
        if st.button("Logout"):
            st.session_state.user = ""
            st.session_state.authenticated = False
            st.rerun()
