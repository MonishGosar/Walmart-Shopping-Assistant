import streamlit as st
from PIL import Image, ImageDraw, ImageEnhance
import google.generativeai as genai
import json
from collections import Counter
import networkx as nx
from gtts import gTTS
import requests

# Configure Gemini API (you'll need to set up your API key)
genai.configure(api_key='AIzaSyAxYQZWcHmDFyKlORuh_v9IJEi7SpahjYc')

# Initialize Gemini model
model = genai.GenerativeModel('gemini-pro')

# Define category areas
category_areas = {
    "Fruits & Vegetables": [(386, 35), (1050, 151)],
    "Deli": [(1052, 35), (1760, 157)],
    "Beverages": [(28, 393), (152, 865)],
    "Dairy": [(26, 868), (154, 1332)],
    "Frozen Foods": [(28, 1338), (152, 1802)],
    "Snacks": [(412, 409), (962, 528)],
    "Condiments & Sauces": [(414, 632), (964, 756)],
    "Dairy Free & Gluten Free": [(412, 852), (961, 979)],
    "Canned Foods": [(1138, 398), (1695, 526)],
    "Pantry Staples": [(1138, 634), (1698, 759)],
    "Dairy Alternatives": [(1140, 849), (1695, 985)],
    "Household Essentials": [(500, 1171), (620, 1802)],
    "Personal Care": [(760, 1176), (869, 1805)],
    "Baby Products": [(1024, 1178), (1142, 1802)],
    "Pet Supplies": [(1288, 1165), (1410, 1800)],
    "Breakfast Foods": [(1547, 1171), (1657, 1797)],
    "Bakery": [(399, 2038), (1064, 2171)],
    "Baking Supplies": [(1065, 2041), (1799, 2171)],
    "Checkout": [(1953, 568), (2455, 1675)],
    "Exit": [(2638, 276), (2754, 650)],
    "Entry": [(2636, 1542), (2756, 1906)]
}

# Load or initialize the item category cache
try:
    with open('item_category_cache.json', 'r') as f:
        item_category_cache = json.load(f)
except FileNotFoundError:
    item_category_cache = {}

def save_cache():
    with open('item_category_cache.json', 'w') as f:
        json.dump(item_category_cache, f)

def get_item_category(item):
    item = item.lower()
    if item in item_category_cache:
        return item_category_cache[item]
    
    categories = list(category_areas.keys())
    prompt = f"""Categorize the grocery item '{item}' into one of the following categories:
    {', '.join(categories)}
    
    Consider these guidelines:
    1. 'Dairy' includes milk, cheese, yogurt, and eggs.
    2. 'Breakfast Foods' includes cereals, oatmeal, and breakfast bars.
    3. 'Pantry Staples' includes flour, sugar, and cooking oils.
    4. 'Snacks' includes chips, cookies, and crackers.
    5. 'Fruits & Vegetables' includes both fresh and frozen produce.
    
    Respond with only the category name, nothing else."""
    
    # Use majority voting
    votes = []
    for _ in range(3):
        response = model.generate_content(prompt)
        votes.append(response.text.strip())
    
    category = Counter(votes).most_common(1)[0][0]
    
    # Cache the result
    item_category_cache[item] = category
    save_cache()
    
    return category

def extract_items_from_input(user_input):
    prompt = f"Extract grocery items from this text: '{user_input}'. Return only the item names, separated by commas."
    response = model.generate_content(prompt)
    return [item.strip() for item in response.text.split(',')]

def highlight_area(image, area):
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    x1, y1 = area[0]
    x2, y2 = area[1]
    translucent_green = (0, 255, 0, 128)  # Green with 50% transparency
    draw.rectangle([x1, y1, x2, y2], fill=translucent_green)
    
    combined = Image.alpha_composite(image.convert('RGBA'), overlay)
    
    return combined

def add_marker(image, area, label):
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    x1, y1 = area[0]
    x2, y2 = area[1]
    translucent_green = (0, 255, 0, 128)
    draw.rectangle([x1, y1, x2, y2], fill=translucent_green)
    
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    draw.text((center_x, center_y), label, fill=(0, 0, 0, 255))
    
    combined = Image.alpha_composite(image.convert('RGBA'), overlay)
    
    return combined

# Define store layout as a graph
def create_store_graph():
    G = nx.Graph()
    # Add nodes for each category
    for category in category_areas.keys():
        G.add_node(category)
    
    # Define connections between areas (simplified for this example)
    connections = [
        ("Entry", "Fruits & Vegetables"),
        ("Fruits & Vegetables", "Deli"),
        ("Fruits & Vegetables", "Beverages"),
        ("Beverages", "Dairy"),
        ("Dairy", "Frozen Foods"),
        ("Deli", "Snacks"),
        ("Snacks", "Condiments & Sauces"),
        ("Condiments & Sauces", "Dairy Free & Gluten Free"),
        ("Snacks", "Canned Foods"),
        ("Canned Foods", "Pantry Staples"),
        ("Pantry Staples", "Dairy Alternatives"),
        ("Dairy Free & Gluten Free", "Household Essentials"),
        ("Household Essentials", "Personal Care"),
        ("Personal Care", "Baby Products"),
        ("Baby Products", "Pet Supplies"),
        ("Pet Supplies", "Breakfast Foods"),
        ("Breakfast Foods", "Bakery"),
        ("Bakery", "Baking Supplies"),
        ("Baking Supplies", "Checkout"),
        ("Checkout", "Exit")
    ]
    G.add_edges_from(connections)
    return G

store_graph = create_store_graph()

def get_optimal_path(categories):
    # Start from Entry and end at Checkout
    path = ["Entry"]
    current = "Entry"
    unvisited = set(categories)
    
    while unvisited:
        # Find the nearest unvisited category
        nearest = min(unvisited, key=lambda x: nx.shortest_path_length(store_graph, current, x))
        # Add the shortest path to this category
        path.extend(nx.shortest_path(store_graph, current, nearest)[1:])
        current = nearest
        unvisited.remove(current)
    
    # Add path to Checkout if not already included
    if path[-1] != "Checkout":
        path.extend(nx.shortest_path(store_graph, current, "Checkout")[1:])
    
    return path

def text_to_speech(text, filename="directions.mp3"):
    tts = gTTS(text=text, lang='en')
    tts.save(filename)
    return filename

def get_directions(categories):
    optimal_path = get_optimal_path(categories)
    
    path_description = " -> ".join(optimal_path)
    items_by_category = {}
    for item in st.session_state.shopping_list:
        category = get_item_category(item)
        if category not in items_by_category:
            items_by_category[category] = []
        items_by_category[category].append(item)
    
    items_description = ", ".join([f"{cat}: {', '.join(items)}" for cat, items in items_by_category.items()])
    
    prompt = f"""Given the following optimal path through a grocery store and the items to be purchased in each category, provide a concise, step-by-step shopping route. Include specific directions (left, right, forward) and mention the items to pick up in each area.

Optimal path: {path_description}

Items by category: {items_description}

Please provide the directions as a numbered list with no more than 6 points. Combine multiple actions into a single step when possible. Start at the entry and end at the checkout.

Example format:
1. Enter store, Move straight and on your right is the bakery aisle.
2. After picking up the items from bakery, move straight and turn right and on your left is the frozen foods.
3. ...
"""

    response = model.generate_content(prompt)
    
    steps = response.text.split('\n')
    directions = [step.strip() for step in steps if step.strip()]
    
    directions_text = " ".join(directions)
    audio_file = text_to_speech(directions_text)
    
    return directions, audio_file

def get_recommendations(item):
    prompt = f"""You are WALBOT, a helpful Walmart store assistant. A customer is interested in {item}.
    Provide 3 specific product recommendations for {item}, including brand names and brief descriptions.
    Also suggest 2 related cross-recommendations that go well with {item}.
    Be friendly and concise in your response.
    
    For each product, provide a URL to an image of that product.
    Use the format [PRODUCT_NAME](IMAGE_URL) for each image suggestion.
    
    Format your response as follows:
    Recommendations for {item}:
    1. [Product 1]
    2. [Product 2]
    3. [Product 3]
    
    You might also like:
    1. [Cross-recommendation 1]
    2. [Cross-recommendation 2]

    Show items in a caroeusel manner
    """
    
    response = model.generate_content(prompt)
    return response.text

def set_walmart_theme():
    st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
    }
    .stButton>button {
        color: #FFFFFF;
        background-color: #0071CE;
        border-radius: 20px;
    }
    .stButton>button:hover {
        background-color: #004C91;
    }
    .stTextInput>div>div>input {
        border-color: #0071CE;
    }
    .stCheckbox>label>div {
 
    }
    h1, h2, h3 {
        color: #0071CE;
    }
    .sidebar .sidebar-content {
        background-color: #FFC220;
    }
    </style>
    """, unsafe_allow_html=True)

def get_chatbot_response(query):
    prompt = f"""You are WALBOT, a helpful Walmart store assistant. A customer has asked the following question:

    {query}

    Please provide a helpful, friendly, and informative response. If the query is about product comparisons, include nutritional information if relevant. If it's about recipes, suggest Walmart products that could be used. Always maintain a helpful and positive tone.

    Limit your response to 150 words. Answwer in bullet points 
    """
    
    response = model.generate_content(prompt)
    return response.text

# Main Streamlit app
def main():
    if 'shopping_list' not in st.session_state:
        st.session_state.shopping_list = []
    if 'map_image' not in st.session_state:
        st.session_state.map_image = None
    if 'directions' not in st.session_state:
        st.session_state.directions = None
    if 'audio_file' not in st.session_state:
        st.session_state.audio_file = None

    st.set_page_config(layout="wide")
    set_walmart_theme()

    st.title("Walmart Smart Shopping Assistant")

    layout_image = Image.open("Layout.png.png")

    # Create a sidebar for input and shopping list
    with st.sidebar:
        

        st.logo("wal.png")

        st.header("Your Shopping List")
        new_item = st.text_input("What would you like to add?")
        if st.button("Add Item(s)", key="add_items_button"):
            if new_item:
                extracted_items = extract_items_from_input(new_item)
                for item in extracted_items:
                    if item not in st.session_state.shopping_list:
                        st.session_state.shopping_list.append(item)
                st.success(f"Added {', '.join(extracted_items)} to your list.")

        for index, item in enumerate(st.session_state.shopping_list):
            if st.checkbox(item, key=f"item_{index}"):
                st.session_state.shopping_list.remove(item)
                st.experimental_rerun()

        if st.button("Clear List", key="clear_list_button"):
            st.session_state.shopping_list = []
            st.session_state.map_image = None
            st.session_state.directions = None
            st.session_state.audio_file = None
            st.success("Shopping list cleared.")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Store Map")
        if st.button("Find Items on Map", key="find_items_button"):
            updated_image = layout_image.copy()
            categories = set()
            for index, item in enumerate(st.session_state.shopping_list):
                category = get_item_category(item)
                if category in category_areas:
                    updated_image = add_marker(updated_image, category_areas[category], str(index + 1))
                    categories.add(category)
                else:
                    st.warning(f"Couldn't find a category for {item}")
            
            st.session_state.map_image = updated_image

        if st.session_state.map_image:
            st.image(st.session_state.map_image, use_column_width=True)
        else:
            st.image(layout_image, use_column_width=True)

    with col2:
        st.header("Your Optimized Route")
        if st.button("Get Directions", key="get_directions_button"):
            categories = set(get_item_category(item) for item in st.session_state.shopping_list)
            st.session_state.directions, st.session_state.audio_file = get_directions(categories)

        if st.session_state.directions:
            for direction in st.session_state.directions:
                st.write(direction)
            
            if st.session_state.audio_file:
                st.audio(st.session_state.audio_file, format='audio/mp3')

    # Add a new section for recommendations
    st.header("Walmart Recommends")

    if st.session_state.shopping_list:
        for item in st.session_state.shopping_list:
            with st.expander(f"Recommendations for {item}"):
                recommendations = get_recommendations(item)
                st.markdown(recommendations)
    else:
        st.info("Add items to your shopping list to see personalized recommendations!")

    # Add chatbot interface
    st.subheader("Ask WALBOT")
    user_query = st.text_input("Ask anything about Walmart products, recipes, or comparisons:")
    if st.button("Get Answer"):
        if user_query:
            with st.spinner("WALBOT is thinking..."):
                response = get_chatbot_response(user_query)
            st.markdown(response)
        else:
            st.warning("Please enter a question for WALBOT.")

    # Add a footer
    st.markdown("---")
    st.markdown("© 2024 Walmart. Save money. Live better.")

if __name__ == "__main__":
    main()