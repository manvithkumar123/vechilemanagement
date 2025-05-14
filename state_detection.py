import re

# Define state prefixes and their full names
STATE_PREFIXES = {
    'TS': 'Telangana',
    'AP': 'Andhra Pradesh',
    'KA': 'Karnataka',
    'TN': 'Tamil Nadu',
    'MH': 'Maharashtra',
    'DL': 'Delhi',
    'HR': 'Haryana',
    'UP': 'Uttar Pradesh',
    'RJ': 'Rajasthan',
    'GJ': 'Gujarat',
    'MP': 'Madhya Pradesh',
    'KL': 'Kerala',
    'PB': 'Punjab',
    'WB': 'West Bengal',
    'OR': 'Odisha',
    'BR': 'Bihar',
    'JH': 'Jharkhand',
    'AS': 'Assam',
    'HP': 'Himachal Pradesh',
    'UK': 'Uttarakhand',
    'GA': 'Goa',
    'CH': 'Chandigarh'
}

def detect_state_from_plate(plate_number):
    """
    Detect state from vehicle registration plate number
    
    Args:
        plate_number: The license plate number as a string
        
    Returns:
        str: The state name or 'Unknown' if state cannot be determined
    """
    if not plate_number:
        return 'Unknown'
    
    # Clean the plate number
    plate = plate_number.strip().upper()
    
    # Extract the first 2 characters
    # In India, license plates typically start with 2 letters indicating the state
    match = re.match(r'^([A-Z]{2})', plate)
    
    if match:
        state_code = match.group(1)
        return STATE_PREFIXES.get(state_code, 'Unknown')
    
    return 'Unknown'
