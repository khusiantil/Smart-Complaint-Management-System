from flask import Flask,render_template,request,redirect,session,jsonify,send_file
from json_db import JSONDatabase
import pickle
import os
import smtplib
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from chatbot import ComplaintChatbot
from datetime import datetime
from llm_classifier import classify_complaint
import csv
import io

load_dotenv()

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0.7
)


app=Flask(__name__)
app.secret_key="secret"

# Initialize JSON Database
db = JSONDatabase("data")

# Initialize Chatbot
try:
    chatbot = ComplaintChatbot()
    chatbot_enabled = True
except Exception as e:
    print(f"Chatbot initialization failed: {e}")
    chatbot_enabled = False

# Initialize LLM Classifier (fallback to ML model if needed)
try:
    model=pickle.load(open("complaint_model.pkl","rb"))
    vector=pickle.load(open("vector.pkl","rb"))
    ml_model_available = True
except:
    ml_model_available = False
    print("ML Model not available, using LLM classifier only")

UPLOAD_FOLDER="static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"]=UPLOAD_FOLDER


def send_email(user_email, message, subject="Smart Complaint System - Update"):
    """Send email to user with customizable subject and message"""
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    if not sender or not password:
        log_msg = f"[WARNING] Skipping email to {user_email}: Setup EMAIL_USER and EMAIL_PASS in .env"
        print(log_msg)
        return False

    try:
        log_msg = f"[EMAIL] Attempting to send email to: {user_email} | Subject: {subject}"
        print(log_msg)
        
        # Create message with UTF-8 encoding to handle emojis and special characters
        msg = MIMEText(message, 'plain', 'utf-8')
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = user_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)

        server.send_message(msg)
        server.quit()
        
        log_msg = f"[SUCCESS] Email successfully sent to {user_email}"
        print(log_msg)
        return True
    except Exception as e:
        log_msg = f"[ERROR] Failed to send email to {user_email}. Error: {type(e).__name__}: {e}"
        print(log_msg)
        return False


@app.route("/")
def home():
    return render_template("index.html")


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            return "Email already exists"
        
        db.insert_user(name, email, password)

        return redirect("/login")

    return render_template("register.html")


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = db.get_user_by_email_password(email, password)

        if user:
            session["user"] = user["name"]
            session["email"] = user["email"]
            return redirect("/dashboard")
        else:
            return "Invalid Login"

    return render_template("login.html")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    # Get statistics
    stats = db.get_complaint_stats()

    return render_template("dashboard.html", 
                          message="",
                          total=stats["total"],
                          pending=stats["pending"],
                          resolved=stats["resolved"])


# ================= COMPLAINT PAGE OPEN - FORM =================
@app.route("/complaint", methods=["GET"])
def complaint_page():

    if "user" not in session:
        return redirect("/login")

    return render_template("complaint_form.html")


# ================= SENTIMENT ANALYSIS =================
def get_sentiment(text):
    text_lower = text.lower()
    angry_keywords = ["angry", "frustrated", "worst", "pathetic", "stupid", "idiot", "terrible", "bad", "sick", "tired", "useless", "disgusting", "horrible", "hell"]
    if any(word in text_lower for word in angry_keywords):
        return "Angry"
    return "Neutral"

# ================= COMPLAINT =================
@app.route("/complaint", methods=["POST"])
def complaint():
    if "user" not in session:
        return redirect("/login")

    text = request.form.get("text", "")
    name = request.form.get("name", "")
    email = request.form.get("email", "")
    contact = request.form.get("contact", "")
    manual_category = request.form.get("manualCategory", "Auto")
    location = request.form.get("location", "")
    lat = request.form.get("lat")
    lng = request.form.get("lng")
    image = request.files.get("image")
    video = request.files.get("video")

    filename = ""
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    video_filename = ""
    if video and video.filename != "":
        video_filename = secure_filename(video.filename)
        video.save(os.path.join(app.config["UPLOAD_FOLDER"], video_filename))

    # Use LLM classifier (with fallback to ML model)
    emotion_state = "Neutral"
    frustration_level = 2
    
    if manual_category == "Auto":
        try:
            # First try LLM classification
            classification = classify_complaint(text)
            category = classification.get('category', 'Other')
            emotion_state = classification.get('emotion_state', 'Neutral')
            frustration_level = classification.get('frustration_level', 2)
            
            print(f"[LLM Classification] Category: {category}, Emotion: {emotion_state}, Frustration: {frustration_level}")
        except Exception as e:
            print(f"LLM Classification failed: {e}, falling back to ML model")
            # Fallback to ML model
            try:
                if ml_model_available:
                    data = vector.transform([text])
                    category = model.predict(data)[0]
                else:
                    category = "Other"
            except:
                category = "Other"
    else:
        category = manual_category

    # DUPLICATE DETECTION
    existing_complaints = [c for c in db.get_all_complaints() if c["status"] in ["Pending", "Reviewing", "In Progress"] and c["category"] == category]
    is_duplicate = False
    for ec in existing_complaints:
        if ec["location"].lower() == location.lower() or (ec.get("lat") == lat and lat is not None):
            is_duplicate = True
            break

    initial_status = "Duplicate" if is_duplicate else "Pending"

    complaint_id = db.insert_complaint(
        text=text, 
        category=category, 
        location=location, 
        image=filename,
        video=video_filename,
        status=initial_status, 
        email=email, 
        lat=lat, 
        lng=lng, 
        name=name, 
        contact=contact,
        emotion_state=emotion_state,
        frustration_level=frustration_level
    )

    # Generate Token ID for tracking
    token_id = chatbot.generate_token_id(name if name else "User", complaint_id)
    
    # Send confirmation email to user
    email_subject = "Complaint Submitted Successfully | Smart Complaint System"
    emotion_note = f"\n📊 Detected Sentiment: {emotion_state} (Frustration Level: {frustration_level}/5)\n" if frustration_level >= 3 else ""
    
    email_body = f"""Hello {name}!

Thank you for submitting your complaint to the Smart Complaint Management System. We have received your complaint and our team will review it shortly.

📋 Complaint Details:
- Token ID: {token_id}
- Complaint ID: {complaint_id}
- Category: {category}
- Location: {location}
- Status: {initial_status}
- Submitted at: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}{emotion_note}

📌 Important: Please save your Token ID and Complaint ID for future reference. You can use them to track the status of your complaint.

{f'Note: A similar issue was already reported in this area. We have marked this as a duplicate to help us prioritize resources. You will still receive updates as the primary complaint is resolved.' if is_duplicate else 'Your complaint has been successfully registered and is now in our queue for processing.'}

We appreciate your patience as we work to resolve this issue. If you have any questions, please feel free to reach out to our support team.

Best regards,
Smart Complaint Management System Team"""
    
    send_email(email, email_body, email_subject)

    msg = "Complaint Submitted! Predicted Category: " + category
    if frustration_level >= 3:
        msg += f" | ⚠️ User appears {emotion_state.lower()}"
    if is_duplicate:
        msg += ". Note: A similar issue was already reported here. It has been marked as a Duplicate!"

    return render_template("dashboard.html", message=msg)


# ================= CHATBOT API - Submit Complaint with Emotion Detection =================
@app.route("/api/chatbot/submit_complaint", methods=["POST"])
def api_submit_complaint_chatbot():
    """API Endpoint for chatbot to submit complaints with emotion analysis"""
    try:
        data = request.get_json()
        
        complaint_text = data.get("text", "")
        name = data.get("name", "")
        email = data.get("email", "")
        contact = data.get("contact", "")
        location = data.get("location", "")
        
        if not complaint_text or not email:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Use LLM classifier with emotion detection
        classification = classify_complaint(complaint_text)
        category = classification.get('category', 'Other')
        emotion_state = classification.get('emotion_state', 'Neutral')
        frustration_level = classification.get('frustration_level', 2)
        
        # Store complaint
        complaint_id = db.insert_complaint(
            text=complaint_text,
            category=category,
            location=location,
            image="",
            status="Pending",
            email=email,
            lat=None,
            lng=None,
            name=name,
            contact=contact,
            emotion_state=emotion_state,
            frustration_level=frustration_level
        )
        
        # Generate Token ID for tracking
        token_id = chatbot.generate_token_id(name if name else "User", complaint_id)
        
        # Send email
        email_subject = "Complaint Submitted Successfully | Smart Complaint System"
        emotion_note = f"\n📊 Detected Sentiment: {emotion_state} (Frustration Level: {frustration_level}/5)\n" if frustration_level >= 3 else ""
        
        email_body = f"""Hello {name}!

Thank you for submitting your complaint via our AI Chatbot. We have received and analyzed your complaint.

📋 Complaint Details:
- Token ID: {token_id}
- Complaint ID: {complaint_id}
- Category: {category}
- Location: {location}
- Status: Pending
- Submitted at: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}{emotion_note}

📌 Important: Please save your Token ID and Complaint ID for tracking purposes.

We will prioritize your complaint and work towards resolution.

Best regards,
Smart Complaint Management System Team"""
        
        send_email(email, email_body, email_subject)
        
        return jsonify({
            "status": "success",
            "token_id": token_id,
            "complaint_id": complaint_id,
            "category": category,
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "message": f"Complaint registered! Predicted category: {category}"
        }), 200
        
    except Exception as e:
        error_msg = f"Chatbot API Error: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": error_msg}), 500


# ================= CHATBOT API - Submit Complaint with Image Upload =================
@app.route("/api/chatbot/submit_complaint_full", methods=["POST"])
def api_submit_complaint_full():
    """API Endpoint for chatbot to submit complaints with image upload"""
    try:
        complaint_text = request.form.get("complaint_text", "")
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        contact = request.form.get("contact", "")
        location = request.form.get("location", "")
        
        if not complaint_text or not email:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Handle image upload
        filename = ""
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
    
    
        
        # Use LLM classifier with emotion detection
        classification = classify_complaint(complaint_text)
        category = classification.get('category', 'Other')
        emotion_state = classification.get('emotion_state', 'Neutral')
        frustration_level = classification.get('frustration_level', 2)
        
        # Store complaint
        complaint_id = db.insert_complaint(
            text=complaint_text,
            category=category,
            location=location,
            image=filename,
            status="Pending",
            email=email,
            lat=None,
            lng=None,
            name=name,
            contact=contact,
            emotion_state=emotion_state,
            frustration_level=frustration_level
        )
        
        # Generate Token ID for tracking
        token_id = chatbot.generate_token_id(name if name else "User", complaint_id)
        
        # Send email
        email_subject = "Complaint Submitted Successfully | Smart Complaint System"
        emotion_note = f"\n📊 Detected Sentiment: {emotion_state} (Frustration Level: {frustration_level}/5)\n" if frustration_level >= 3 else ""
        
        email_body = f"""Hello {name}!

Thank you for submitting your complaint via our AI Chatbot. We have received and analyzed your complaint.

📋 Complaint Details:
- Token ID: {token_id}
- Complaint ID: {complaint_id}
- Category: {category}
- Location: {location}
- Status: Pending
- Submitted at: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}{emotion_note}

📌 Important: Please save your Token ID and Complaint ID for tracking purposes.

We will prioritize your complaint and work towards resolution.

Best regards,
Smart Complaint Management System Team"""
        
        send_email(email, email_body, email_subject)
        
        return jsonify({
            "status": "success",
            "token_id": token_id,
            "complaint_id": complaint_id,
            "category": category,
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "message": f"Complaint registered! Predicted category: {category}"
        }), 200
        
    except Exception as e:
        error_msg = f"Chatbot API Error (Full): {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": error_msg}), 500


# ================= CHATBOT API - Submit Complaint with Files (Image/Video) =================
@app.route("/api/chatbot/submit_complaint_with_files", methods=["POST"])
def api_submit_complaint_with_files():
    """API Endpoint for chatbot to submit complaints with files (image/video)"""
    try:
        print("\n=== ChatBot File Upload Debug ===")
        print(f"Request method: {request.method}")
        print(f"Request content type: {request.content_type}")
        print(f"Request form keys: {list(request.form.keys())}")
        print(f"Request files keys: {list(request.files.keys())}")
        
        text = request.form.get("text", "")
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        contact = request.form.get("contact", "")
        location = request.form.get("location", "")
        image = request.files.get("image")
        video = request.files.get("video")

        print(f"Form data - text: {text[:50]}..., name: {name}, email: {email}, contact: {contact}, location: {location}")
        print(f"Files - image: {image}, video: {video}")

        image_filename = ""
        if image and image.filename != "":
            print(f"Saving image: {image.filename}")
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
            print(f"Image path: {image_path}")
            image.save(image_path)
            print(f"Image saved successfully: {image_path}")

        video_filename = ""
        if video and video.filename != "":
            print(f"Saving video: {video.filename}")
            video_filename = secure_filename(video.filename)
            video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_filename)
            print(f"Video path: {video_path}")
            video.save(video_path)
            print(f"Video saved successfully: {video_path}")

        # Use LLM to classify complaint
        print("Classifying complaint with LLM...")
        try:
            classification = classify_complaint(text)
            category = classification.get('category', 'Other')
            emotion_state = classification.get('emotion_state', 'Neutral')
            frustration_level = classification.get('frustration_level', 2)
            print(f"Classification successful: category={category}, emotion={emotion_state}, frustration={frustration_level}")
        except Exception as e:
            print(f"Classification error: {e}")
            category = "Other"
            emotion_state = "Neutral"
            frustration_level = 2

        # Insert complaint with files
        print("Inserting complaint into database...")
        complaint_id = db.insert_complaint(
            text=text,
            category=category,
            location=location,
            image=image_filename,
            video=video_filename,
            status="Pending",
            email=email,
            lat=None,
            lng=None,
            name=name,
            contact=contact,
            emotion_state=emotion_state,
            frustration_level=frustration_level
        )
        print(f"Complaint inserted: ID={complaint_id}")

        # Generate Token ID
        print("Generating token ID...")
        token_id = chatbot.generate_token_id(name if name else "User", complaint_id)
        print(f"Token ID generated: {token_id}")

        # Send confirmation email
        email_subject = "Complaint Submitted via Chatbot | Smart Complaint System"
        media_note = ""
        if image_filename and video_filename:
            media_note = "\n📎 Media: Photo + Video attached\n"
        elif image_filename:
            media_note = "\n📎 Media: Photo attached\n"
        elif video_filename:
            media_note = "\n📎 Media: Video attached\n"

        email_body = f"""Hello {name}!

Your complaint has been successfully submitted via our AI Chatbot.

📋 Complaint Details:
- Token ID: {token_id}
- Complaint ID: {complaint_id}
- Category: {category}
- Location: {location}
- Status: Pending
{media_note}
💭 Sentiment: {emotion_state} (Level {frustration_level}/5)

We will prioritize and process your complaint shortly.

Best regards,
Smart Complaint Management System"""

        print(f"Sending email to {email}...")
        send_email(email, email_body, email_subject)
        print("Email sent successfully")

        print(f"Returning success response...")
        return jsonify({
            "status": "success",
            "token_id": token_id,
            "complaint_id": complaint_id,
            "category": category,
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "message": "Complaint registered with media!"
        }), 200

    except Exception as e:
        print(f"\n!!! CHATBOT FILE UPLOAD ERROR !!!")
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())
        print("!!! END ERROR !!!\n")
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500


# ================= CHATBOT API - Analyze Emotion =================
@app.route("/api/chatbot/analyze_emotion", methods=["POST"])
def api_analyze_emotion():
    """API Endpoint to analyze user's emotional state"""
    try:
        data = request.get_json()
        complaint_text = data.get("text", "")
        
        if not complaint_text:
            return jsonify({"status": "error", "message": "No text provided"}), 400
        
        # Use LLM classifier to get emotion
        classification = classify_complaint(complaint_text)
        
        return jsonify({
            "status": "success",
            "emotion_state": classification.get('emotion_state', 'Neutral'),
            "frustration_level": classification.get('frustration_level', 2),
            "category": classification.get('category', 'Other'),
            "confidence": classification.get('confidence', 0.7)
        }), 200
        
    except Exception as e:
        print(f"Emotion Analysis Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ================= API - CHECK COMPLAINT STATUS =================
@app.route("/api/chatbot/check_status", methods=["POST"])
def api_check_status():
    """API Endpoint to check complaint status using Token ID"""
    try:
        data = request.get_json()
        token_id = data.get("token_id", "").strip()
        
        if not token_id:
            return jsonify({
                "status": "error",
                "complaint_found": False,
                "message": "Token ID is required"
            }), 400
        
        # Search for complaint with matching token (format: COMP-name-id-hex)
        # Extract complaint ID from token
        all_complaints = db.get_all_complaints()
        found_complaint = None
        
        parts = token_id.split("-")
        if len(parts) >= 4:
            try:
                extracted_id = int(parts[-2])
                for complaint in all_complaints:
                    if complaint["id"] == extracted_id:
                        found_complaint = complaint
                        break
            except ValueError:
                pass
        
        if found_complaint:
            return jsonify({
                "status": "success",
                "complaint_found": True,
                "token_id": token_id,
                "complaint_id": found_complaint["id"],
                "complaint_status": found_complaint.get("status", "Pending"),
                "response": f"""📋 COMPLAINT STATUS REPORT

🎫 Token ID: {token_id}
📝 Complaint ID: {found_complaint['id']}
📂 Category: {found_complaint.get('category', 'Unknown')}
📍 Location: {found_complaint.get('location', 'Unknown')}
👤 Name: {found_complaint.get('name', 'Unknown')}
📧 Email: {found_complaint.get('email', 'Unknown')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STATUS: {found_complaint.get('status', 'Pending')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 Description:
{found_complaint.get('text', 'N/A')}

💭 Emotion: {found_complaint.get('emotion_state', 'Neutral')}
⚠️ Frustration Level: {found_complaint.get('frustration_level', 2)}/5

📅 Submitted: {found_complaint.get('created_at', 'Unknown')}

✅ Your complaint has been registered and is being processed.
Thank you for your patience!"""
            }), 200
        else:
            return jsonify({
                "status": "error",
                "complaint_found": False,
                "message": f"❌ No complaint found with Token ID: {token_id}",
                "response": f"Could not find a complaint matching '{token_id}'."
            }), 404
        
    except Exception as e:
        print(f"Check Status Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "complaint_found": False,
            "message": f"Error checking status: {str(e)}"
        }), 500


# ================= CHATBOT API - General Query Handler (LLM-Powered Help) =================
@app.route("/api/chatbot/query", methods=["POST"])
def api_chatbot_query():
    """API Endpoint for general queries using LLM"""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({
                "status": "error",
                "message": "Message is required"
            }), 400
        
        if not chatbot_enabled:
            return jsonify({
                "status": "error",
                "message": "Chatbot service is temporarily unavailable. Please try again later."
            }), 503
        
        # Use LLM to generate response
        result = chatbot.chat_general_query(user_message)
        
        if result["status"] == "success":
            return jsonify({
                "status": "success",
                "response": result["response"],
                "message": "Query processed successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.get("message", "Error processing query")
            }), 500
    
    except Exception as e:
        print(f"Chatbot Query Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Error processing query: {str(e)}"
        }), 500


# ================= ADMIN LOGIN =================
# ================= DEPARTMENT CREDENTIALS =================
DEPARTMENT_CREDENTIALS = {
    "electricity": "ElecAdmin@2026",
    "water": "WaterAdmin@2026",
    "road": "RoadAdmin@2026",
    "cleanliness": "CleanAdmin@2026",
    "drainage": "DrainAdmin@2026",
    "admin": "MainAdmin@2026"
}

DEPARTMENT_MAP = {
    "electricity": "Electricity",
    "water": "Water",
    "road": "Road",
    "cleanliness": "Cleanliness",
    "drainage": "Drainage",
    "admin": "All"
}

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").lower()
        password = request.form.get("password", "")
        
        # Check if username and password match
        if username in DEPARTMENT_CREDENTIALS and DEPARTMENT_CREDENTIALS[username] == password:
            session["admin_logged_in"] = True
            session["department"] = DEPARTMENT_MAP[username]
            session["admin_username"] = username
            
            # Redirect to appropriate admin panel
            if username == "admin":
                return redirect("/admin")
            else:
                return redirect(f"/admin/{username}")
        else:
            return render_template("admin_login.html", error="❌ Invalid Department ID or Password")
    return render_template("admin_login.html")

def get_priority(text):
    text = text.lower()
    urgent_keywords = ["urgent", "danger", "fire", "leak", "broken", "wire", "current", "accident", "immediate", "emergency", "dead", "die", "short circuit", "spark"]
    if any(keyword in text for keyword in urgent_keywords):
        return "High"
    return "Normal"

# ================= ADMIN =================
@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    all_complaints = db.get_all_complaints()
    department = session.get("department", "All")
    
    # Filter by department
    if department != "All":
        complaints = [c for c in all_complaints if c["category"] == department]
        total = len(complaints)
        pending = len([c for c in complaints if c["status"] not in ["Resolved", "Duplicate"]])
        resolved = len([c for c in complaints if c["status"] == "Resolved"])
        stats = {"total": total, "pending": pending, "resolved": resolved}
    else:
        complaints = all_complaints
        stats = db.get_complaint_stats()
    
    processed_complaints = []
    for c in complaints:
        priority = get_priority(c["text"])
        
        # Check if another complaint is a duplicate of this one, if so bump priority
        duplicates = [dup for dup in all_complaints if dup["status"] == "Duplicate" and dup["location"].lower() == c["location"].lower() and dup["category"] == c["category"]]
        if len(duplicates) > 0 and c["status"] != "Duplicate":
            priority = "High"
        
        # Get emotion state (for LLM-classified complaints)
        emotion_state = c.get("emotion_state", "Neutral")
        frustration_level = c.get("frustration_level", 2)
        
        # Bump priority if user is frustrated
        if frustration_level >= 4:
            priority = "High"

        processed_complaints.append({
            "id": c["id"],
            "text": c["text"],
            "category": c["category"],
            "location": c["location"],
            "image": c["image"],
            "video": c.get("video", ""),
            "status": c["status"],
            "priority": priority,
            "sentiment": get_sentiment(c["text"]),
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "name": c.get("name", "Unknown"),
            "email": c.get("email", "")
        })
        
    def sort_key(c):
        status_order = 2 if c["status"] == "Resolved" else (1 if c["status"] == "Duplicate" else 0)
        priority_order = 0 if c["priority"] == "High" else 1
        return (status_order, priority_order, -c["id"])

    processed_complaints.sort(key=sort_key)

    return render_template("admin.html", complaints=processed_complaints, stats=stats, department=department)

# ================= STATUS UPDATE =================
@app.route("/update/<int:id>/<status>")
def update_status(id, status):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    admin_dept = session.get("department", "All")
    if admin_dept != "All":
        all_complaints = db.get_all_complaints()
        complaint = next((c for c in all_complaints if c["id"] == id), None)
        if complaint and complaint.get("category") != admin_dept:
            return redirect("/admin")

    # Only allow safe statuses
    if status in ["Pending", "Reviewing", "In Progress", "Resolved", "Duplicate"]:
        db.update_complaint_status(id, status)
        
        # Find complaint and send email notification
        for c in db.get_all_complaints():
            if c["id"] == id and c.get("email"):
                
                # Determine email message based on status
                if status == "Resolved":
                    email_body = f"""Hello!

Great news! Your complaint has been RESOLVED by our admin team.

Complaint Details:
- Category: {c['category']}
- Location: {c['location']}
- Previous Status: {c['status']}
- New Status: RESOLVED

Thank you for using the Smart Complaint System. Your feedback helps us improve!"""
                    send_email(c["email"], email_body, "Complaint Resolved")
                
                elif status == "In Progress":
                    email_body = f"""Hello!

Your complaint is now being actively worked on by our team.

Complaint Details:
- Category: {c['category']}
- Location: {c['location']}
- Previous Status: {c['status']}
- New Status: IN PROGRESS

Our team is investigating and will resolve this shortly.

Thank you for your patience!"""
                    send_email(c["email"], email_body, "Complaint Status Update: In Progress")
                
                elif status == "Reviewing":
                    email_body = f"""Hello!

Your complaint is under review by our team.

ðŸ“‹ Complaint Details:
- Category: {c['category']}
- Location: {c['location']}
- Previous Status: {c['status']}
- New Status: ðŸ“ REVIEWING

We are reviewing the details and will take appropriate action.

Thank you for reporting this!"""
                    send_email(c["email"], email_body, "Complaint Status Update: Under Review ðŸ“")
                
                elif status == "Duplicate":
                    email_body = f"""Hello!

Your complaint has been marked as a DUPLICATE.

ðŸ“‹ Complaint Details:
- Category: {c['category']}
- Location: {c['location']}
- Status: âš ï¸ DUPLICATE

A similar issue was already reported at this location. We are already working on resolving it!

Thank you for your vigilance!"""
                    send_email(c["email"], email_body, "Complaint Status Update: Duplicate âš ï¸")
                
                break

    return redirect("/admin")
    
# ================= ADMIN MAP DASHBOARD =================
@app.route("/admin_map")
def admin_map():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")
        
    complaints = db.get_all_complaints()
    department = session.get("department", "All")
    if department != "All":
        complaints = [c for c in complaints if c["category"] == department]
        
    return render_template("map.html", complaints=complaints)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= DELETE COMPLAINT =================
@app.route("/delete_complaint/<int:complaint_id>", methods=["POST"])
def delete_complaint(complaint_id):
    """Delete a complaint from the system"""
    if not session.get("admin_logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    admin_dept = session.get("department", "All")
    if admin_dept != "All":
        all_complaints = db.get_all_complaints()
        complaint = next((c for c in all_complaints if c["id"] == complaint_id), None)
        if complaint and complaint.get("category") != admin_dept:
            return jsonify({"status": "error", "message": "Unauthorized: Cannot delete other department's complaint"}), 403

    try:
        db.delete_complaint(complaint_id)
        return jsonify({"status": "success", "message": f"Complaint #{complaint_id} has been deleted successfully"})    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================= ADMIN LOGOUT =================
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    return redirect("/admin_login")


# ================= CSV EXPORT FUNCTIONALITY =================

@app.route("/export_csv")
def export_csv():
    """Export all complaints as CSV file"""
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")
    
    try:
        # Get all complaints
        all_complaints = db.get_all_complaints()
        
        # Filter by department if admin is viewing a specific department
        admin_dept = session.get("department", "All")
        if admin_dept != "All":
            all_complaints = [c for c in all_complaints if c["category"].lower() == admin_dept.lower()]
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID',
            'Complaint Text',
            'Category',
            'Location',
            'Status',
            'Name',
            'Email',
            'Contact',
            'Emotion State',
            'Frustration Level',
            'Image',
            'Video',
            'Latitude',
            'Longitude',
            'Date'
        ])
        
        # Write complaints data
        for c in all_complaints:
            writer.writerow([
                c.get('id', ''),
                c.get('text', ''),
                c.get('category', ''),
                c.get('location', ''),
                c.get('status', ''),
                c.get('name', ''),
                c.get('email', ''),
                c.get('contact', ''),
                c.get('emotion_state', 'Unknown'),
                c.get('frustration_level', ''),
                c.get('image', ''),
                c.get('video', ''),
                c.get('lat', ''),
                c.get('lng', ''),
                c.get('date', '')
            ])
        
        # Create response
        output.seek(0)
        bytes_output = io.BytesIO()
        bytes_output.write(output.getvalue().encode('utf-8'))
        bytes_output.seek(0)
        
        # Generate filename with department and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if admin_dept != "All":
            filename = f"complaints_{admin_dept}_{timestamp}.csv"
        else:
            filename = f"complaints_all_{timestamp}.csv"
        
        return send_file(
            bytes_output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        print(f"CSV Export Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ================= DEPARTMENT-SPECIFIC ADMIN DASHBOARDS =================

def render_department_admin(department_name):
    """Render admin dashboard for a specific department"""
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")
        
    admin_dept = session.get("department", "All")
    if admin_dept != "All" and admin_dept.lower() != department_name.lower():
        return redirect("/admin")
    
    all_complaints = db.get_all_complaints()
    
    # Filter by department
    complaints = [c for c in all_complaints if c["category"].lower() == department_name.lower()]
    
    total = len(complaints)
    pending = len([c for c in complaints if c["status"] not in ["Resolved", "Duplicate"]])
    resolved = len([c for c in complaints if c["status"] == "Resolved"])
    stats = {"total": total, "pending": pending, "resolved": resolved}
    
    processed_complaints = []
    for c in complaints:
        priority = get_priority(c["text"])
        
        # Check if another complaint is a duplicate
        duplicates = [dup for dup in all_complaints if dup["status"] == "Duplicate" and dup["location"].lower() == c["location"].lower() and dup["category"] == c["category"]]
        if len(duplicates) > 0 and c["status"] != "Duplicate":
            priority = "High"
        
        emotion_state = c.get("emotion_state", "Neutral")
        frustration_level = c.get("frustration_level", 2)
        
        if frustration_level >= 4:
            priority = "High"

        processed_complaints.append({
            "id": c["id"],
            "text": c["text"],
            "category": c["category"],
            "location": c["location"],
            "image": c["image"],
            "video": c.get("video", ""),
            "status": c["status"],
            "priority": priority,
            "sentiment": get_sentiment(c["text"]),
            "emotion_state": emotion_state,
            "frustration_level": frustration_level,
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "name": c.get("name", "Unknown"),
            "email": c.get("email", "")
        })
    
    def sort_key(c):
        status_order = 2 if c["status"] == "Resolved" else (1 if c["status"] == "Duplicate" else 0)
        priority_order = 0 if c["priority"] == "High" else 1
        return (status_order, priority_order, -c["id"])

    processed_complaints.sort(key=sort_key)
    
    return render_template("admin.html", complaints=processed_complaints, stats=stats, department=department_name)


# Electricity Department Admin
@app.route("/admin/electricity")
def admin_electricity():
    """Electricity Department Admin Dashboard"""
    return render_department_admin("Electricity")


# Water Department Admin
@app.route("/admin/water")
def admin_water():
    """Water Department Admin Dashboard"""
    return render_department_admin("Water")


# Road Department Admin
@app.route("/admin/road")
def admin_road():
    """Road Department Admin Dashboard"""
    return render_department_admin("Road")


# Cleanliness Department Admin
@app.route("/admin/cleanliness")
def admin_cleanliness():
    """Cleanliness Department Admin Dashboard"""
    return render_department_admin("Cleanliness")


# Drainage Department Admin
@app.route("/admin/drainage")
def admin_drainage():
    """Drainage Department Admin Dashboard"""
    return render_department_admin("Drainage")


# =========================================================
# ================= NEW ROUTES ADDED BELOW ================
# =========================================================

# My Complaints
@app.route("/my_complaints")
def my_complaints():

    if "user" not in session:
        return redirect("/login")

    complaints = db.get_complaints_by_email(session["email"])
    
    # Convert to list format expected by template
    complaints_list = []
    for complaint in complaints:
        complaints_list.append((
            complaint["id"],
            complaint["text"],
            complaint["category"],
            complaint["location"],
            complaint["image"],
            complaint["status"],
            complaint.get("video", "")
        ))

    return render_template("my_complaints.html", complaints=complaints_list)


# Status Page
@app.route("/status")
def status():
    return render_template("status.html")


# Category Filter
@app.route("/category/<cat>")
def category_page(cat):

    complaints = db.get_complaints_by_category(cat)
    
    # Convert to list format expected by template
    complaints_list = []
    for complaint in complaints:
        complaints_list.append((
            complaint["id"],
            complaint["text"],
            complaint["category"],
            complaint["location"],
            complaint["image"],
            complaint["status"]
        ))

    return render_template("category.html",
                           complaints=complaints_list,
                           category=cat)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/road")
def road():
    return render_template("road.html")


@app.route("/submit_road_complaint", methods=["POST"])
def submit_road_complaint():

    title = request.form['title']
    road_type = request.form['road_type']
    location = request.form['location']
    district = request.form['district']
    pincode = request.form['pincode']
    severity = request.form['severity']
    date_observed = request.form['date_observed']
    description = request.form['description']

    photo = request.files['photo']

    filename = secure_filename(photo.filename)
    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    db.insert_road_complaint(
        title=title,
        road_type=road_type,
        location=location,
        district=district,
        pincode=pincode,
        severity=severity,
        date_observed=date_observed,
        description=description,
        photo=filename,
        status="Pending"
    )

    return "Complaint Successfully Registered!"


# Reports Page
@app.route("/reports")
def reports():

    stats = db.get_complaint_stats()
    
    return render_template("reports.html",
                           total=stats["total"],
                           pending=stats["pending"],
                           resolved=stats["resolved"])


# Settings Page
@app.route("/settings")
def settings():

    if "user" not in session:
        return redirect("/login")

    return render_template("settings.html")


# ================= CHATBOT PAGE =================

@app.route("/chatbot")
def chatbot_page():
    """Render chatbot interface"""
    return render_template("chatbot.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Simple chat endpoint for frontend"""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({"reply": "Please provide a message."}), 400
        
        if not chatbot_enabled:
            return jsonify({"reply": "Chatbot service is temporarily unavailable. Please try again later."}), 503
        
        # Use LLM to generate response
        result = chatbot.chat_general_query(user_message)
        
        if result["status"] == "success":
            return jsonify({"reply": result["response"]}), 200
        else:
            return jsonify({"reply": "Sorry, I couldn't process your request. Please try again."}), 500
    
    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({"reply": "An error occurred. Please try again."}), 500


if __name__ == "__main__":
    app.run(debug=True)
