import subprocess
import json
import requests
import os

def test_omdb(title, year):
    api_key = "acdaf73"
    omdb_url = f"http://www.omdbapi.com/?apikey={api_key}&t={requests.utils.quote(title)}&y={year}&type=movie"
    
    cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "5", omdb_url]
    res = subprocess.run(cmd, capture_output=True, timeout=10)
    
    result = {
        "title": title,
        "year": year,
        "url": omdb_url,
        "returncode": res.returncode,
        "response": None,
        "error": None
    }
    
    if res.returncode == 0 and res.stdout:
        try:
            result["response"] = json.loads(res.stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            result["error"] = f"Parse error: {str(e)}"
    else:
        result["error"] = res.stderr.decode('utf-8', errors='ignore') if res.stderr else "No output"
        
    return result

if __name__ == "__main__":
    titles = [
        ("Mystery 101: Deadly History", "2021"),
        ("Stolen by My Mother: The Kamiyah Mobley Story", "2020"),
        ("Stolen Baby: The Murder of Heidi Broussard", "2023")
    ]
    
    results = []
    for t, y in titles:
        results.append(test_omdb(t, y))
        
    with open("test_omdb_output.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("Results written to test_omdb_output.json")
