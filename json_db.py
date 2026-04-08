import json
import os
from datetime import datetime

class JSONDatabase:
    def __init__(self, db_name="data"):
        self.db_name = db_name
        self.db_path = f"{db_name}.json"
        self.ensure_db_exists()
    
    def ensure_db_exists(self):
        """Create database file if it doesn't exist"""
        if not os.path.exists(self.db_path):
            initial_data = {
                "users": [],
                "complaints": [],
                "road_complaints": []
            }
            with open(self.db_path, 'w') as f:
                json.dump(initial_data, f, indent=4)
    
    def load_data(self):
        """Load all data from JSON file"""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading data: {e}")
            return {"users": [], "complaints": [], "road_complaints": []}
    
    def save_data(self, data):
        """Save data to JSON file"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def insert_user(self, name, email, password):
        """Insert a new user"""
        data = self.load_data()
        user_id = len(data["users"]) + 1
        user = {
            "id": user_id,
            "name": name,
            "email": email,
            "password": password,
            "created_at": datetime.now().isoformat()
        }
        data["users"].append(user)
        self.save_data(data)
        return user_id
    
    def get_user_by_email_password(self, email, password):
        """Get user by email and password"""
        data = self.load_data()
        for user in data["users"]:
            if user["email"] == email and user["password"] == password:
                return user
        return None
    
    def get_user_by_email(self, email):
        """Get user by email"""
        data = self.load_data()
        for user in data["users"]:
            if user["email"] == email:
                return user
        return None
    
    def insert_complaint(self, text, category, location, image, status="Pending", email="", lat=None, lng=None, contact="", name="", emotion_state="Neutral", frustration_level=2, video=""):
        """Insert a new complaint"""
        data = self.load_data()
        complaint_id = len(data["complaints"]) + 1
        complaint = {
            "id": complaint_id,
            "text": text,
            "category": category,
            "location": location,
            "image": image,
            "video": video,
            "status": status,
            "email": email,
            "contact": contact,
            "name": name,
            "lat": lat,
            "lng": lng,
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "created_at": datetime.now().isoformat()
        }
        data["complaints"].append(complaint)
        self.save_data(data)
        return complaint_id
    
    def get_all_complaints(self):
        """Get all complaints"""
        data = self.load_data()
        return data["complaints"]
    
    def get_complaints_by_category(self, category):
        """Get complaints by category"""
        data = self.load_data()
        return [c for c in data["complaints"] if c["category"] == category]
    
    def get_complaints_by_email(self, email):
        """Get complaints by user email"""
        data = self.load_data()
        return [c for c in data["complaints"] if c["email"] == email]
    
    def update_complaint_status(self, complaint_id, status):
        """Update complaint status"""
        data = self.load_data()
        for complaint in data["complaints"]:
            if complaint["id"] == complaint_id:
                complaint["status"] = status
                complaint["updated_at"] = datetime.now().isoformat()
                self.save_data(data)
                return True
        return False
    
    def delete_complaint(self, complaint_id):
        """Delete a complaint by ID"""
        data = self.load_data()
        original_length = len(data["complaints"])
        data["complaints"] = [c for c in data["complaints"] if c["id"] != complaint_id]
        
        if len(data["complaints"]) < original_length:
            self.save_data(data)
            return True
        return False
    
    def get_complaint_stats(self):
        """Get complaint statistics"""
        data = self.load_data()
        complaints = data["complaints"]
        total = len(complaints)
        pending = len([c for c in complaints if c["status"] == "Pending"])
        resolved = len([c for c in complaints if c["status"] == "Resolved"])
        return {"total": total, "pending": pending, "resolved": resolved}
    
    def insert_road_complaint(self, title, road_type, location, district, pincode, 
                             severity, date_observed, description, photo, status="Pending"):
        """Insert road complaint"""
        data = self.load_data()
        complaint_id = len(data["road_complaints"]) + 1
        complaint = {
            "id": complaint_id,
            "title": title,
            "road_type": road_type,
            "location": location,
            "district": district,
            "pincode": pincode,
            "severity": severity,
            "date_observed": date_observed,
            "description": description,
            "image": photo,
            "status": status,
            "created_at": datetime.now().isoformat()
        }
        data["road_complaints"].append(complaint)
        self.save_data(data)
        return complaint_id
    
    def get_all_road_complaints(self):
        """Get all road complaints"""
        data = self.load_data()
        return data["road_complaints"]
    
    def update_road_complaint_status(self, complaint_id, status):
        """Update road complaint status"""
        data = self.load_data()
        for complaint in data["road_complaints"]:
            if complaint["id"] == complaint_id:
                complaint["status"] = status
                complaint["updated_at"] = datetime.now().isoformat()
                self.save_data(data)
                return True
        return False
    
    def get_all_users(self):
        """Get all users"""
        data = self.load_data()
        return data["users"]
