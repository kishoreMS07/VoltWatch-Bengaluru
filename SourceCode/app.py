"""VoltWatch Bengaluru - Flask server.  Run: python app.py  ->  http://127.0.0.1:5000"""
from flask import Flask, jsonify, render_template, abort
from voltwatch.pipeline import Pipeline

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def no_cache(resp):
    # always serve the latest HTML/JS/CSS (avoids stale cached copies)
    resp.headers["Cache-Control"] = "no-store"
    return resp
pipe = Pipeline()          # loads data, learns baselines, trains the model, scores all stations (~6 s)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fleet")
def fleet():
    return jsonify(pipe.fleet())


@app.route("/api/station/<sid>")
def station(sid):
    r = pipe.results.get(sid.upper())
    if r is None:
        abort(404)
    return jsonify(r)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
