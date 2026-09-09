from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Temporary databases (resets when the app restarts)
client_requests = []
registered_pros = []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/client", methods=["GET", "POST"])
def client_page():
    if request.method == "POST":
        name = request.form.get("name")
        address = request.form.get("address")
        details = request.form.get("details")
        
        if name and address and details:
            client_requests.append({
                "name": name,
                "address": address,
                "details": details
            })
        return redirect(url_for("client_page"))
        
    return render_template("client.html", requests=client_requests)

@app.route("/professional", methods=["GET", "POST"])
def professional_page():
    if request.method == "POST":
        name = request.form.get("name")
        trade = request.form.get("trade")
        address = request.form.get("address")
        
        if name and trade and address:
            registered_pros.append({
                "name": name,
                "trade": trade,
                "address": address
            })
        return redirect(url_for("professional_page"))
        
    return render_template("professional.html", pros=registered_pros, requests=client_requests)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
