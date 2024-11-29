import streamlit as st
import os
import requests
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import zipfile

# Function to fetch content (with dynamic rendering support)
def fetch_content(url, dynamic=False):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        if dynamic:
            # Use httpx with a rendering service for dynamic content
            # Replace the API URL below with your preferred rendering service
            rendering_service = "https://render-tron.appspot.com/render"
            response = httpx.get(f"{rendering_service}/{url}", timeout=30)
            response.raise_for_status()
            return response.text
        else:
            # Use standard requests for static pages
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
    except Exception as e:
        raise RuntimeError(f"Failed to fetch content: {e}")

# Function to clone a webpage
def clone_website(url, output_dir, dynamic=False, depth=1):
    visited = set()
    os.makedirs(output_dir, exist_ok=True)
    links_to_process = [url]

    for current_depth in range(depth):
        new_links = []
        for link in links_to_process:
            if link not in visited:
                try:
                    # Fetch content
                    html_content = fetch_content(link, dynamic=dynamic)
                    soup = BeautifulSoup(html_content, "html.parser")

                    # Save HTML
                    parsed_url = urlparse(link)
                    page_dir = os.path.join(output_dir, parsed_url.netloc)
                    os.makedirs(page_dir, exist_ok=True)
                    file_name = "index.html" if parsed_url.path == "/" else parsed_url.path.strip("/") + ".html"
                    html_path = os.path.join(page_dir, file_name)
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(soup.prettify())

                    # Download resources
                    download_resources(soup, page_dir, link)

                    # Find new links for recursive crawling
                    new_links.extend([
                        urljoin(link, a.get("href")) for a in soup.find_all("a", href=True)
                        if urlparse(a.get("href")).netloc in link
                    ])

                    visited.add(link)
                except Exception as e:
                    st.warning(f"Error processing {link}: {e}")

        links_to_process = new_links
    return f"Website cloned successfully at: {output_dir}"

# Function to download resources (CSS, JS, Images)
def download_resources(soup, output_dir, base_url):
    # Download CSS
    for css in soup.find_all("link", rel="stylesheet"):
        href = css.get("href")
        if href:
            download_file(urljoin(base_url, href), output_dir)

    # Download JS
    for js in soup.find_all("script", src=True):
        src = js.get("src")
        if src:
            download_file(urljoin(base_url, src), output_dir)

    # Download Images
    for img in soup.find_all("img", src=True):
        src = img.get("src")
        if src:
            download_file(urljoin(base_url, src), output_dir)

# Function to download a single file
def download_file(file_url, output_dir):
    try:
        response = requests.get(file_url, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        file_name = os.path.basename(urlparse(file_url).path)
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        st.warning(f"Failed to download {file_url}: {e}")

# Function to compress the cloned website
def compress_website(output_dir, zip_file_path):
    try:
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)
        return f"Cloned website compressed successfully at: {zip_file_path}"
    except Exception as e:
        return f"Error compressing website: {e}"

# Streamlit App
st.title("Advanced Website Cloner with Dynamic Rendering")
st.sidebar.header("Settings")
website_url = st.text_input("Enter the website URL:", "https://example.com")
output_folder = st.text_input("Enter output folder path:", "./cloned_website")
depth = st.slider("Cloning Depth (for recursive cloning):", 1, 3, 1)
dynamic_rendering = st.checkbox("Enable Dynamic Rendering (for JavaScript-heavy sites)")
compress = st.checkbox("Compress Cloned Website into ZIP")

# Cloning Feature
if st.button("Start Cloning"):
    with st.spinner("Cloning in progress..."):
        try:
            result = clone_website(website_url, output_folder, dynamic=dynamic_rendering, depth=depth)
            st.success(result)
            if compress:
                zip_file = os.path.join(output_folder, "cloned_website.zip")
                compress_result = compress_website(output_folder, zip_file)
                st.success(compress_result)
        except Exception as e:
            st.error(f"Error: {e}")

st.sidebar.info("Use responsibly. This tool clones websites for offline analysis and replication.")
