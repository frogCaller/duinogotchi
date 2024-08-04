import sys
import os
import json
import time
import requests
import subprocess
import socket
import random
from datetime import datetime
from waveshare_epd import epd2in13_V3
from PIL import Image, ImageDraw, ImageFont
import faces
import psutil

##############################################
##    ADD YOUR DUINO-COIN USERNAME BELOW    ##
##############################################
username = "USERNAME"

# Screen rotation
screen_rotate = 0

# Duino-Coin API URL
api_url = "https://server.duinocoin.com/v3/users/" + username

# List to store faces for different conditions
myface = []
quotes_list = []

last_quote_update_time = 0
current_quote = ""
first_run = True

def get_cpu_memory_usage():
    cpu_usage = psutil.cpu_percent()
    memory_info = psutil.virtual_memory()
    memory_usage = memory_info.percent
    return cpu_usage, memory_usage

# Function to read quotes from quotes.txt
def read_quotes():
    global quotes_list
    try:
        with open("quotes.txt", "r") as file:
            quotes_list = file.readlines()
        quotes_list = [quote.strip() for quote in quotes_list if quote.strip()] 
    except FileNotFoundError:
        print("quotes.txt file not found.")

# Function to get a new quote every 10 seconds
def get_new_quotes():
    global current_quote, first_run
    if first_run:
        first_run = False
        current_quote = "New day, new coin"
    elif quotes_list:
        # Select one random quote from the list
        current_quote = random.choice(quotes_list)
    else:
        current_quote = "No quotes available"
    return current_quote

# Initial call to read quotes from the file
read_quotes()

# Function to get the current time
def get_current_time():
    now = datetime.now()
    day = now.strftime("%A").upper()
    date = now.strftime("%m/%d/%y")
    time_str = now.strftime("%I:%M %p")
    return f"{day}  {time_str}\n{date}"

# Function to get CPU temperature
def get_cpu_temperature():
    try:
        cpu_temp = os.popen("vcgencmd measure_temp").readline()
        return cpu_temp.replace("temp=", "").replace("'","°")
    except:
        return False

# Function to get Wi-Fi status
def get_wifi_status():
    try:
        subprocess.check_output(['ping', '-c', '1', '8.8.8.8'])
        return "WIFI: OK"
    except subprocess.CalledProcessError:
        return "WIFI: NOT OK"

# Function to format hashrate
def format_hashrate(hashrate):
    if hashrate >= 1_000_000_000:
        return f"{hashrate / 1_000_000_000:.2f} GH/s"
    elif hashrate >= 1_000_000:
        return f"{hashrate / 1_000_000:.2f} MH/s"
    elif hashrate >= 1_000:
        return f"{hashrate / 1_000:.2f} KH/s"
    else:
        return f"{hashrate:.2f} H/s"
      
def get_duco_data():
    url = "https://server.duinocoin.com/api.json"
    response = requests.get(url)
    data = response.json()
    return data

# Global variable to track if Duino Coin data was fetched
duco_data_fetched = False

def fetch_duco_user_data():
    global duco_data_fetched
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        result = data['result']

        # Extract the relevant information
        balance = result['balance']['balance']
        stake_amount = result['balance'].get('stake_amount', 0)
        stake_date_timestamp = result['balance'].get('stake_date', 'N/A')
        if stake_date_timestamp != 'N/A':
            stake_date = datetime.fromtimestamp(stake_date_timestamp)
            formatted_stake_date = stake_date.strftime("%m/%d/%Y")
        else:
            formatted_stake_date = 'N/A'
        trust_score = result['balance'].get('trust_score', 'N/A')
        total_hashrate = sum(miner['hashrate'] for miner in result['miners'])
        formatted_hashrate = format_hashrate(total_hashrate)
        achievements = len(result['achievements'])
        miners = {miner['identifier'] for miner in result['miners']}
        pools = {miner['pool'] for miner in result['miners']}

        duco_data_fetched = True  # Set the flag to True after fetching data

        return {
            "balance": balance,
            "stake_amount": stake_amount,
            "formatted_stake_date": formatted_stake_date,
            "trust_score": trust_score,
            "formatted_hashrate": formatted_hashrate,
            "achievements": achievements,
            "miners": miners,
            "pools": pools
        }

    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        duco_data_fetched = False  # Ensure flag is False if there's an error
        return None

def update_face(user_data, first_run):
    global duco_data_fetched  # Use the global variable

    # Reset the face list
    myface.clear()
    wifi_status = get_wifi_status()
    cpu_temp = get_cpu_temperature()
    cpu_temp_value = float(cpu_temp.replace("°C", "")) if cpu_temp else None

    # Determine face based on conditions
    if wifi_status == "NET ERROR":
        myface.append(faces.SAD)
    elif user_data["formatted_hashrate"] == "0.00 H/s":
        myface.append(faces.BORED)
    elif cpu_temp_value and cpu_temp_value >= 72:
        current_time = int(time.time())
        if current_time % 2 == 0:
            myface.append(faces.HOT)
        else:
            myface.append(faces.HOT2)
    elif user_data["formatted_hashrate"] != "0.00 H/s":
        if first_run:
            myface.append(faces.AWAKE)
        elif duco_data_fetched:  # Check if Duino Coin data was recently fetched
            myface.append(faces.COOL)
            duco_data_fetched = False  # Reset the flag after showing the COOL face
        else:
            current_time = int(time.time())
            state = current_time // 3 % 17  # 17 states excluding COOL
            if state in [0, 1, 2, 3]:  # LOOK_L twice
                myface.append(faces.LOOK_R)
            elif state in [4, 5, 6, 7]:  # LOOK_R twice
                myface.append(faces.LOOK_L)
            elif state in [8]:  # AWAKE twice
                myface.append(faces.SLEEP)
            elif state in [9, 10, 11, 12]:  # LOOK_L_HAPPY four times
                myface.append(faces.LOOK_R_HAPPY)
            elif state in [13, 14, 15, 16]:  # LOOK_R_HAPPY four times
                myface.append(faces.LOOK_L_HAPPY)
            else:  # Additional states to add more variety
                myface.append(faces.HAPPY)
    else:
        myface.append(faces.HAPPY)  # Default happy face

def display_duco_data(epd, user_data, duco_data, cpu_temp, cpu_usage, memory_usage):
    global current_quote  # Use the global current_quote
    total_miners = len(user_data["miners"])
    
    font10 = ImageFont.truetype('Font.ttc', 10)
    font12 = ImageFont.truetype('Font.ttc', 12)
    font15 = ImageFont.truetype('Font.ttc', 15)
    face32 = ImageFont.truetype(('DejaVuSansMono.ttf'), 32)

    image = Image.new('1', (epd.height, epd.width), 255)
    draw = ImageDraw.Draw(image)

    # Drawing the template
    draw.rectangle((0, 0, 250, 122), fill=255)
    draw.text((2, 1), f"DUINO-COIN", font=font10, fill=0)
    draw.text((80, 1), get_wifi_status(), font=font10, fill=0)

    draw.text((5, 15), f"{username}>", font=font12, fill=0)
    # Display current face
    if myface:
        draw.text((5, 28), myface[0], font=face32, fill=0)

    draw.text((135, 1), "MINER: ON" if user_data["formatted_hashrate"] != "0.00 H/s" else "MINER: OFF", font=font10, fill=0)
    draw.text((200, 1), datetime.now().strftime("%-I:%M %p"), font=font10, fill=0)  # Use the updated CPU temperature
    draw.line([(0, 13), (250, 13)], fill=0, width=1)

    # Update current_quote if CPU temperature is too high
    if myface and myface[0] == faces.HOT:
        current_quote = "It's getting hot!"
        
    # Display additional duco_data
    duco_price = duco_data.get('Duco price')
    duco_s1_hashrate = duco_data.get('DUCO-S1 hashrate')
    
    if duco_price is not None:
        draw.text((5, 75), f"Price: ${duco_price:.8f}", font=font12, fill=0)
    else:
        draw.text((5, 75), "Price: N/A", font=font10, fill=0)

    if duco_s1_hashrate is not None:
        draw.text((5, 90), f"DUCO-S1 HR: {duco_s1_hashrate}", font=font10, fill=0)
    else:
        draw.text((5, 90), "DUCO-S1 HR: N/A", font=font10, fill=0)
    
    # Display new quotes
    draw.text((125, 55), current_quote, font=font12, fill=0)

    # Determine the appropriate font based on the balance value
    if user_data['balance'] > 9999.999:
      balance_font = font12  # Use a smaller font
    else:
      balance_font = font15  # Use the standard font

    # Draw the balance text with the chosen font
    draw.text((125, 17), f"{user_data['balance']:.3f} DUCO", font=balance_font, fill=0)
    draw.text((125, 37), f"{user_data['formatted_hashrate']}", font=font12, fill=0)
    
    draw.line([(0, 108), (250, 108)], fill=0, width=1)
    
# Calculate positions based on text widths using textbbox
    label_y = 75  # Starting y position
    value_y = 85  # Starting y position for values
    label_x = 140  # Starting x position for labels
    spacing = 10  # Spacing between labels and values

# Get the width of each label
    mem_label_width = draw.textbbox((0, 0), "mem", font=font10)[2]
    cpu_label_width = draw.textbbox((0, 0), "cpu", font=font10)[2]
    temp_label_width = draw.textbbox((0, 0), "temp", font=font10)[2]

# Calculate x positions for labels
    cpu_label_x = label_x + mem_label_width + spacing
    temp_label_x = cpu_label_x + cpu_label_width + spacing

# Calculate x positions for values
    mem_value_x = label_x
    cpu_value_x = cpu_label_x
    temp_value_x = temp_label_x

# Draw labels horizontally
    draw.text((label_x, label_y), "mem", font=font10, fill=0)
    draw.text((cpu_label_x, label_y), "cpu", font=font10, fill=0)
    draw.text((temp_label_x, label_y), "temp", font=font10, fill=0)

# Draw values horizontally
    draw.text((mem_value_x, value_y), f"{memory_usage:.1f}%", font=font10, fill=0)
    draw.text((cpu_value_x, value_y), f"{cpu_usage:.0f}%", font=font10, fill=0)
    draw.text((temp_value_x, value_y), f"{cpu_temp}", font=font10, fill=0)
    
# Display pool name and hashrate
    draw.text((2, 110), f"STAKE: {user_data['stake_amount']:.3f}", font=font10, fill=0)
    draw.text((80, 110), f"RCV: {user_data['formatted_stake_date']}", font=font10, fill=0)
    draw.text((180, 110), f"W: {total_miners}  |  A: {user_data['achievements']}", font=font10, fill=0)

# Rotate and display the image    
    image = image.rotate(screen_rotate)
    epd.displayPartial(epd.getbuffer(image))

def main():
    epd = epd2in13_V3.EPD()
    epd.init()
    epd.Clear(0xFF)

    last_fetch_time = 0
    last_face_update_time = 0
    last_quote_update_time = 0
    last_cpu_temp_update_time = 0
    user_data = None
    duco_data = None
    cpu_temp = None 
    cpu_usage = None
    memory_usage = None
    first_run = True 

    while True:
        current_time = time.time()
        
        if current_time - last_cpu_temp_update_time >= 3:
            cpu_temp = get_cpu_temperature()
            cpu_usage, memory_usage = get_cpu_memory_usage()  # Get CPU and memory usage
            last_cpu_temp_update_time = current_time
        
        # Fetch Duino-Coin user data and duco_data every 60 seconds
        if current_time - last_fetch_time >= 60:
            user_data = fetch_duco_user_data()
            duco_data = get_duco_data() 
            last_fetch_time = current_time

        # Update face every 2 seconds
        if current_time - last_face_update_time >= 3:
            if user_data:
                update_face(user_data, first_run) 
                first_run = False  
            last_face_update_time = current_time

        # Update quotes every 10 seconds
        if current_time - last_quote_update_time >= 10:
            current_quote = get_new_quotes() 
            last_quote_update_time = current_time

        # Display data and quotes
        if user_data and duco_data:
            display_duco_data(epd, user_data, duco_data, cpu_temp, cpu_usage, memory_usage) 
        else:
            print("Failed to retrieve Duino-Coin user data")

        time.sleep(2)

if __name__ == "__main__":
    main()
