<div align="center">

# 🏀 DeutschifyNBA

*Elevate your basketball news experience with DeutschifyNBA, an innovative web application that seamlessly adapts NBA news into A1-level German, enhanced with AI-driven adaptations and immersive text-to-speech features.*

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

</div>

## ✨ Features

### 🎯 Core Functionality
- **Real-time NBA News** - Stay updated with the latest basketball content, expertly translated to A1-level German.
- **AI-Powered Text Adaptation** - Tailored content designed to aid German language learners at the beginner level.
- **Text-to-Speech** - Experience articles audibly in German, enhancing comprehension and pronunciation.
- **Learning Support** - Enrich your vocabulary with curated lists and comprehension exercises.

### 🎨 User Interface
- **Modern Design** - Enjoy a sleek, responsive layout that adapts to your viewing preferences.
- **Dark Mode** - Switch to a darker theme for a comfortable reading experience.
- **Interactive Elements** - Engage with smooth animations and transitions for a dynamic user experience.
- **Mobile-First** - Optimized for seamless access across all devices.

### 🛠 Technical Features
- **RESTful API** - Access well-documented endpoints for seamless integration.
- **Caching System** - Benefit from enhanced performance with efficient caching.
- **Error Handling** - Experience robust error management for uninterrupted service.
- **Logging** - Monitor system performance with comprehensive logging capabilities.

## 🚀 Quick Start

### Prerequisites 
- **Python 3.9 or higher** - Ensure you have Python installed on your machine. You can download it from [python.org](https://www.python.org/downloads/).
- **FastAPI** - This application is built on FastAPI. Install it using pip:
  ```bash
  pip install fastapi
  ```
- **Uvicorn** - A lightning-fast ASGI server for serving your FastAPI application:
  ```bash
  pip install uvicorn
  ```
- **OpenAI API Key** - Sign up at [OpenAI](https://openai.com/) and obtain your API key to access AI features.
- **Bootstrap** - For styling, ensure you have Bootstrap included in your project. You can add it via CDN in your HTML or install it through npm.

### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/deutschifytelegram.git
   ```
2. Navigate to the project directory:
   ```bash
   cd deutschifytelegram
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

Now you're ready to start adapting NBA news into A1-level German!

## 🔍 Backend Logic Overview

The backend of DeutschifyTelegram is designed to efficiently process NBA news articles and adapt them into A1-level German for language learners. Here’s a step-by-step breakdown of the logic:

### 1. **User Request**
- When a user accesses the application, they can request the latest NBA news articles through the frontend interface.
- The request is sent to the FastAPI backend via a RESTful API endpoint.

### 2. **Fetching NBA News**
- The backend retrieves the latest NBA news articles from a reliable sports news API or database.
- This can involve making an HTTP request to an external API that provides real-time sports news.

### 3. **Text Processing**
- Once the articles are fetched, the backend processes the text to prepare it for adaptation. This involves:
  - **Cleaning the Text**: Removing any unnecessary HTML tags, advertisements, or irrelevant content.
  - **Extracting Key Information**: Identifying the main points of the articles that are relevant for adaptation.

### 4. **AI-Powered Adaptation**
- The core of the adaptation process involves using the OpenAI API:
  - The cleaned and extracted text is sent to the OpenAI API with specific instructions to adapt the content to A1-level German.
  - The API utilizes natural language processing to simplify complex sentences, replace difficult vocabulary with simpler alternatives, and ensure that the overall message remains intact while being accessible to A1 learners.

### 5. **Receiving Adapted Text**
- The backend receives the adapted text from the OpenAI API.
- This adapted content is then formatted and prepared for delivery back to the user.

### 6. **Response to User**
- The backend sends the adapted A1-level German text back to the frontend as a JSON response.
- The frontend then displays the adapted articles to the user, allowing them to read and engage with the content.

### 7. **Additional Features**
- **Text-to-Speech**: Users can listen to the adapted articles using the text-to-speech feature, which is integrated into the frontend.
- **Learning Support**: The backend can also provide additional resources, such as vocabulary lists and comprehension exercises, based on the adapted text.

