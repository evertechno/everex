import os
import requests
import httpx
import json
import zipfile
from urllib.parse import urljoin, urlparse, urlsplit
from bs4 import BeautifulSoup
import streamlit as st
import google.generativeai as genai
import mimetypes
import base64
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configure Google Gemini AI
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Function to fetch website content (with dynamic rendering support)
def fetch_content(url, dynamic=False, timeout=10):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        if dynamic:
            # Using Rendertron for JavaScript-rendered content
            rendering_service = "https://render-tron.appspot.com/render"
            response = httpx.get(f"{rendering_service}/{url}", timeout=timeout)
            response.raise_for_status()
            return response.text
        else:
            # Regular static content scraping
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
    except requests.exceptions.Timeout:
        raise RuntimeError("Request timed out while fetching content.")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch content: {e}")

# Function to analyze content with AI
def analyze_content_with_ai(content):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        summary = model.generate_content(f"Summarize the following content: {content[:4000]}")
        return summary.text
    except Exception as e:
        return f"AI Analysis Error: {e}"

# Function to extract SEO metadata
def extract_seo_metadata(soup):
    metadata = {
        "title": soup.title.string if soup.title else "No Title",
        "description": soup.find("meta", attrs={"name": "description"})["content"] if soup.find("meta", attrs={"name": "description"}) else "No Description",
        "keywords": soup.find("meta", attrs={"name": "keywords"})["content"] if soup.find("meta", attrs={"name": "keywords"}) else "No Keywords"
    }
    return metadata

# Function to clone a website
def clone_website(url, output_dir, dynamic=False, timeout=10):
    os.makedirs(output_dir, exist_ok=True)
    try:
        html_content = fetch_content(url, dynamic=dynamic, timeout=timeout)
        soup = BeautifulSoup(html_content, "html.parser")

        # Save the HTML file
        parsed_url = urlparse(url)
        file_path = os.path.join(output_dir, "index.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(soup.prettify())

        # Extract resources (CSS, JS, images)
        download_resources(soup, output_dir, url)

        # Analyze content with AI
        summary = analyze_content_with_ai(html_content)

        # Extract SEO metadata
        seo_metadata = extract_seo_metadata(soup)

        return {"summary": summary, "seo_metadata": seo_metadata, "path": output_dir, "html_content": html_content}
    except Exception as e:
        return {"error": str(e)}

# Function to download resources (CSS, JS, images, fonts, etc.)
def download_resources(soup, output_dir, base_url):
    # Download CSS, JS, images, and other resources
    for css in soup.find_all("link", rel="stylesheet"):
        href = css.get("href")
        if href:
            download_file(urljoin(base_url, href), output_dir)

    for js in soup.find_all("script", src=True):
        src = js.get("src")
        if src:
            download_file(urljoin(base_url, src), output_dir)

    for img in soup.find_all("img", src=True):
        src = img.get("src")
        if src:
            download_file(urljoin(base_url, src), output_dir)

    for font in soup.find_all("link", rel="stylesheet", href=True):
        href = font.get("href")
        if href:
            download_file(urljoin(base_url, href), output_dir)

# Function to handle file downloading with retries
def download_file(file_url, output_dir, retries=3):
    try:
        response = requests.get(file_url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        file_name = os.path.basename(urlparse(file_url).path)
        file_path = os.path.join(output_dir, file_name)
        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        return file_path
    except Exception as e:
        st.warning(f"Failed to download {file_url}: {e}")
        return None

# Function to compress the cloned website into a ZIP file
def compress_website(output_dir, zip_file_path):
    try:
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)
        return zip_file_path
    except Exception as e:
        return None

# Function to export content in different formats (HTML, JSON, Python, JS)
def export_content(content, export_format, output_dir):
    if export_format == "HTML":
        file_name = "cloned_website.html"
        with open(os.path.join(output_dir, file_name), "w", encoding="utf-8") as f:
            f.write(content["html_content"])
        return file_name

    elif export_format == "JSON":
        json_data = json.dumps(content, indent=4)
        file_name = "cloned_website.json"
        with open(os.path.join(output_dir, file_name), "w", encoding="utf-8") as f:
            f.write(json_data)
        return file_name

    elif export_format == "Python":
        python_code = f'''
import requests

url = "{content["url"]}"

response = requests.get(url)
print(response.text)
'''
        file_name = "cloned_website.py"
        with open(os.path.join(output_dir, file_name), "w", encoding="utf-8") as f:
            f.write(python_code)
        return file_name

    elif export_format == "JavaScript":
        js_code = f'''
fetch("{content["url"]}")
    .then(response => response.text())
    .then(data => console.log(data))
    .catch(error => console.error("Error:", error));
'''
        file_name = "cloned_website.js"
        with open(os.path.join(output_dir, file_name), "w", encoding="utf-8") as f:
            f.write(js_code)
        return file_name

# Streamlit App
st.title("AI-Enhanced Website Cloner & Analyzer")
st.sidebar.header("Settings")
website_url = st.text_input("Enter the website URL:", "https://example.com")
output_folder = st.text_input("Enter output folder path:", "./cloned_website")
dynamic_rendering = st.checkbox("Enable Dynamic Rendering")
compress = st.checkbox("Compress Cloned Website into ZIP")
export_format = st.selectbox("Choose export format:", ["HTML", "JSON", "Python", "JavaScript"])

if st.button("Start Cloning"):
    with st.spinner("Cloning and analyzing in progress..."):
        result = clone_website(website_url, output_folder, dynamic=dynamic_rendering)
        if "error" in result:
            st.error(f"Error: {result['error']}")
        else:
            st.success("Website cloned and analyzed successfully!")
            st.write("### AI Summary of Content:")
            st.write(result["summary"])
            st.write("### SEO Metadata:")
            st.json(result["seo_metadata"])

            # Export the content in the selected format
            exported_file = export_content(result, export_format, output_folder)

            # Provide a download button for the exported file
            export_file_path = os.path.join(output_folder, exported_file)
            with open(export_file_path, "rb") as file:
                st.download_button(
                    label=f"Download {export_format} File",
                    data=file,
                    file_name=exported_file,
                    mime="application/octet-stream"
                )

            if compress:
                zip_file = os.path.join(output_folder, "cloned_website.zip")
                zip_path = compress_website(output_folder, zip_file)
                if zip_path:
                    st.success(f"Cloned website compressed successfully at: {zip_path}")
                    with open(zip_path, "rb") as zip_file:
                        st.download_button("Download ZIP", data=zip_file, file_name="cloned_website.zip")

# Prompt-based AI Interaction
st.sidebar.subheader("AI Content Assistant")
prompt = st.text_area("Ask AI about the cloned website content:", "What are the key takeaways?")
if st.button("Ask AI"):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        ai_response = model.generate_content(f"Analyze this website content: {prompt}")
        st.write("### AI Response:")
        st.write(ai_response.text)
    except Exception as e:
        st.error(f"AI Interaction Error: {e}")
