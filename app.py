import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from google import genai

app = Flask(__name__)

# Configure PostgreSQL Database
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
geolocator = Nominatim(user_agent="nova_dispatch_app")

# Initialize Gemini Client
gemini_key = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=gemini_key) if gemini_key else None

# Database Models
class ClientRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False, default="")
    address = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False, default="")
    phone = db.Column(db.String(50), nullable=False, default="")
    details = db.Column(db.Text, nullable=False)
    detected_trade = db.Column(db.String(100), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    assigned_pro_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50), default="PENDING")

class Professional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trade = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.String(200), nullable=True, default="")
    city = db.Column(db.String(100), nullable=False, default="")
    address = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False, default="")
    phone = db.Column(db.String(50), nullable=False, default="")
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)

with app.app_context():
    db.create_all()

def classify_trade_with_ai(problem_description):
    """Uses Gemini to identify trade. Returns None if unclassifiable/unmatched."""
    if not ai_client:
        return None
    
    prompt = (
        "You are an emergency dispatch AI. Read this client issue description and classify "
        "the single most relevant trade required from these exact options: "
        "['Plumber', 'Electrician', 'Locksmith', 'HVAC / Heating']. "
        "If the issue does not clearly fit any of these categories, respond strictly with 'NONE'. "
        "Respond ONLY with the exact trade name or 'NONE'.\n\n"
        f"Client issue: {problem_description}"
    )
    
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        trade = response.text.strip()
        allowed_trades = ["Plumber", "Electrician", "Locksmith", "HVAC / Heating"]
        for allowed in allowed_trades:
            if allowed.lower() in trade.lower():
                return allowed
        return None
    except Exception:
        return None

def get_coords(full_address_str):
    try:
        location = geolocator.geocode(full_address_str, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/client", methods=["GET", "POST"])
def client_page():
    if request.method == "POST":
        name = request.form.get("name")
        city = request.form.get("city")
        address = request.form.get("address")
        email = request.form.get("email")
        phone = request.form.get("phone")
        details = request.form.get("details")
        
        full_addr = f"{address}, {city}"
        lat, lon = get_coords(full_addr)
        detected_trade = classify_trade_with_ai(details)
        
        if name and address and details:
            new_request = ClientRequest(
                name=name, 
                city=city,
                address=address, 
                email=email,
                phone=phone,
                details=details, 
                detected_trade=detected_trade,
                lat=lat, 
                lon=lon
            )
            db.session.add(new_request)
            db.session.commit()
            return redirect(url_for("matches_page", request_id=new_request.id))
            
    return render_template("client.html")

@app.route("/matches/<int:request_id>")
def matches_page(request_id):
    client_req = ClientRequest.query.get_or_404(request_id)
    
    # Strict matching rule: If trade not recognized or no pros exist for trade, return empty
    matching_pros = []
    if client_req.detected_trade:
        matching_pros = Professional.query.filter_by(trade=client_req.detected_trade).all()
    
    nearby_pros = []
    for pro in matching_pros:
        dist_km = None
        if client_req.lat and client_req.lon and pro.lat and pro.lon:
            dist_km = round(geodesic((client_req.lat, client_req.lon), (pro.lat, pro.lon)).km, 1)
        
        nearby_pros.append({
            "pro": pro,
            "distance": dist_km if dist_km is not None else "Unknown"
        })
    
    nearby_pros.sort(key=lambda x: x["distance"] if isinstance(x["distance"], (int, float)) else 9999)
    return render_template("matches.html", client_req=client_req, pros=nearby_pros)

@app.route("/accept_job/<int:request_id>/<int:pro_id>", methods=["POST"])
def accept_job(request_id, pro_id):
    client_req = ClientRequest.query.get_or_404(request_id)
    client_req.assigned_pro_id = pro_id
    client_req.status = "ACCEPTED"
    db.session.commit()
    return redirect(url_for("tracking_page", request_id=request_id))

@app.route("/tracking/<int:request_id>")
def tracking_page(request_id):
    client_req = ClientRequest.query.get_or_404(request_id)
    pro = Professional.query.get(client_req.assigned_pro_id) if client_req.assigned_pro_id else None
    return render_template("tracking.html", client_req=client_req, pro=pro)

@app.route("/professional", methods=["GET", "POST"])
def professional_page():
    if request.method == "POST":
        name = request.form.get("name")
        trade = request.form.get("trade")
        skills = request.form.get("skills")
        city = request.form.get("city")
        address = request.form.get("address")
        email = request.form.get("email")
        phone = request.form.get("phone")
        
        full_addr = f"{address}, {city}"
        lat, lon = get_coords(full_addr)
        
        if name and trade and address:
            new_pro = Professional(
                name=name, 
                trade=trade, 
                skills=skills,
                city=city,
                address=address, 
                email=email,
                phone=phone,
                lat=lat, 
                lon=lon
            )
            db.session.add(new_pro)
            db.session.commit()
            
        return redirect(url_for("professional_page"))
        
    pros = Professional.query.all()
    requests = ClientRequest.query.all()
    return render_template("professional.html", pros=pros, requests=requests)

@app.route("/delete_pro/<int:pro_id>", methods=["POST"])
def delete_pro(pro_id):
    pro = Professional.query.get_or_404(pro_id)
    db.session.delete(pro)
    db.session.commit()
    return redirect(url_for("professional_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
