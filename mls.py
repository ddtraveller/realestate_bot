import json
import os
import time
import requests
import logging
import argparse
from typing import Dict, List, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('real_estate_analyzer')

class SimplyRetsAPI:
    """
    Client for interacting with the SimplyRETS API
    """
    def __init__(self, username=None, password=None):
        """Initialize the API client with credentials"""
        # Get credentials from environment variables if not provided
        self.username = username or os.environ.get('SIMPLYRETS_USERNAME', 'simplyrets')
        self.password = password or os.environ.get('SIMPLYRETS_PASSWORD', 'simplyrets')
        self.base_url = "https://api.simplyrets.com"
        
    def get_properties(self, params=None):
        """
        Get properties from the SimplyRETS API
        
        Args:
            params (dict): Query parameters for filtering properties
        
        Returns:
            list: List of property objects
        """
        url = f"{self.base_url}/properties"
        
        # Default parameters if none provided
        if params is None:
            params = {
                "limit": 25,
                "sort": "listprice"
            }
        
        try:
            logger.info(f"Making SimplyRETS API request to {url} with params: {params}")
            response = requests.get(
                url,
                auth=(self.username, self.password),
                params=params
            )
            
            logger.info(f"SimplyRETS response status code: {response.status_code}")
            
            if response.status_code == 200:
                properties = response.json()
                logger.info(f"Successfully retrieved {len(properties)} properties")
                return properties
            elif response.status_code == 401:
                logger.error("Authentication failed. Please check your SimplyRETS credentials.")
                raise ValueError("Authentication failed. Please check your SimplyRETS credentials.")
            else:
                logger.error(f"Error: {response.status_code}, Response: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching properties: {str(e)}")
            raise
    
    def get_property_by_id(self, mls_id):
        """
        Get a specific property by its MLS ID
        
        Args:
            mls_id (str): The MLS ID of the property
            
        Returns:
            dict: Property details or None if not found
        """
        url = f"{self.base_url}/properties/{mls_id}"
        
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password)
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error retrieving property {mls_id}: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving property: {str(e)}")
            return None
            
    def get_properties_metadata(self, vendor=None):
        """
        Get metadata about the properties available in the feed using OPTIONS request
        
        Args:
            vendor (str, optional): Vendor parameter for multiple feeds
            
        Returns:
            dict: Metadata about the properties in the feed
        """
        url = f"{self.base_url}/properties"
        params = {}
        if vendor:
            params['vendor'] = vendor
            
        try:
            logger.info(f"Making OPTIONS request to {url}")
            response = requests.options(
                url,
                auth=(self.username, self.password),
                params=params
            )
            
            logger.info(f"OPTIONS request response status code: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error retrieving metadata: {response.status_code}, {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error retrieving metadata: {str(e)}")
            return {}


def extract_property_data(properties: List[Dict]) -> List[Dict]:
    """
    Extract relevant data from properties for analysis
    
    Args:
        properties (list): List of property objects from the API
        
    Returns:
        list: List of simplified property data for analysis
    """
    simplified_properties = []
    
    for prop in properties:
        try:
            # Calculate price per square foot
            square_feet = prop.get("property", {}).get("area", 0) or 0
            list_price = prop.get("listPrice", 0) or 0
            price_per_sqft = None
            if square_feet > 0 and list_price > 0:
                price_per_sqft = round(list_price / square_feet, 2)
            
            # Calculate price drop percentage
            original_price = prop.get("originalListPrice", 0) or 0
            price_drop_percent = None
            if original_price > 0 and list_price > 0 and original_price > list_price:
                price_drop_percent = round(((original_price - list_price) / original_price) * 100, 2)
            
            # Get location data
            lat = prop.get("geo", {}).get("lat")
            lng = prop.get("geo", {}).get("lng")
            
            # Extract key property information
            property_info = {
                "mlsId": prop.get("mlsId"),
                "listingId": prop.get("listingId", ""),
                "address": prop.get('address', {}).get('full', 'N/A'),
                "city": prop.get('address', {}).get('city', ''),
                "state": prop.get('address', {}).get('state', ''),
                "zip": prop.get('address', {}).get('postalCode', ''),
                "county": prop.get('address', {}).get('country', ''),
                "price": prop.get("listPrice"),
                "originalPrice": prop.get("originalListPrice"),
                "bedrooms": prop.get("property", {}).get("bedrooms"),
                "bathrooms": (prop.get("property", {}).get("bathsFull", 0) or 0) + 
                             ((prop.get("property", {}).get("bathsHalf", 0) or 0) * 0.5),
                "squareFeet": square_feet,
                "pricePerSqFt": price_per_sqft,
                "yearBuilt": prop.get("property", {}).get("yearBuilt"),
                "propertyType": prop.get("property", {}).get("type"),
                "propertySubType": prop.get("property", {}).get("subType"),
                "lotSize": prop.get("property", {}).get("lotSize"),
                "stories": prop.get("property", {}).get("stories"),
                "garageSpaces": prop.get("property", {}).get("garageSpaces"),
                "hasPool": "pool" in (prop.get("property", {}).get("exteriorFeatures", "").lower() or ""),
                "remarks": prop.get("remarks", "")[:200] + "..." if prop.get("remarks") else "",
                "photos": len(prop.get("photos", [])),
                "priceDrop": (prop.get("originalListPrice", 0) - prop.get("listPrice", 0)) 
                             if prop.get("originalListPrice") and prop.get("listPrice") else 0,
                "priceDropPercent": price_drop_percent,
                "interiorFeatures": prop.get("property", {}).get("interiorFeatures", ""),
                "exteriorFeatures": prop.get("property", {}).get("exteriorFeatures", ""),
                "latitude": lat,
                "longitude": lng
            }
            
            simplified_properties.append(property_info)
        except Exception as e:
            logger.error(f"Error processing property: {str(e)}")
            continue
    
    return simplified_properties


def analyze_properties_with_huggingface(properties: List[Dict], api_key: str) -> Dict:
    """
    Use Hugging Face model to analyze properties and find interesting ones
    
    Args:
        properties (list): List of simplified property data
        api_key (str): Hugging Face API key
        
    Returns:
        dict: Analysis results with interesting properties
    """
    # Create a detailed property summary for the top 10 properties (to keep prompt size manageable)
    property_sample = properties[:10]
    property_summary = json.dumps(property_sample, indent=2)
    
    # Create statistics about the full set
    price_stats = {
        "count": len(properties),
        "min_price": min([p.get("price", 0) for p in properties if p.get("price") is not None], default=0),
        "max_price": max([p.get("price", 0) for p in properties if p.get("price") is not None], default=0),
        "avg_price": sum([p.get("price", 0) or 0 for p in properties if p.get("price") is not None]) / 
                    len([p for p in properties if p.get("price") is not None]) if properties else 0
    }
    
    # Add average price per square foot if available
    properties_with_sqft = [p for p in properties if p.get("pricePerSqFt") is not None]
    if properties_with_sqft:
        price_stats["avg_price_per_sqft"] = sum([p.get("pricePerSqFt", 0) or 0 for p in properties_with_sqft]) / len(properties_with_sqft)
    
    # Find properties with significant price drops
    price_drops = [p for p in properties if p.get("priceDropPercent") is not None and p.get("priceDropPercent") > 3]
    price_drops.sort(key=lambda p: p.get("priceDropPercent", 0) or 0, reverse=True)
    price_drop_summary = json.dumps(price_drops[:5], indent=2) if price_drops else "No significant price drops"
    
    # Find properties with good value (price per square foot below average)
    good_value = []
    if "avg_price_per_sqft" in price_stats:
        good_value = [p for p in properties if p.get("pricePerSqFt") is not None and 
                    p.get("pricePerSqFt") < price_stats["avg_price_per_sqft"] * 0.9]
        good_value.sort(key=lambda p: p.get("pricePerSqFt") or float('inf'))
    value_summary = json.dumps(good_value[:5], indent=2) if good_value else "No standout value properties"
    
    # Find properties with unique features
    unique_features = [p for p in properties if 
                      p.get("hasPool") or 
                      "fireplace" in (p.get("interiorFeatures", "").lower() or "") or
                      "view" in (p.get("exteriorFeatures", "").lower() or "")]
    features_summary = json.dumps(unique_features[:5], indent=2) if unique_features else "No properties with standout features"
    
    # Create a prompt for the AI model
    prompt = f"""You are a real estate analysis expert. Analyze the following properties and identify the most interesting ones for a real estate agent to look at. 

Here are statistics for the entire portfolio of {len(properties)} properties:
{json.dumps(price_stats, indent=2)}

Focus on:
1. Properties with high value relative to their price (good deals)
2. Properties with unique or special features
3. Properties that have had significant price drops
4. Properties in desirable neighborhoods
5. Any anomalies or special opportunities in the market

Sample of properties (10 out of {len(properties)}):
{property_summary}

Properties with significant price drops:
{price_drop_summary}

Properties with good value (below average price per square foot):
{value_summary}

Properties with unique features:
{features_summary}

Provide a detailed analysis with specific properties that stand out and explain why they're worth looking at. Include the MLS ID and address of each property you highlight.
Your analysis should be practical and actionable for a real estate professional. Highlight at least 3-5 specific properties and explain their unique value propositions.

Analysis:"""

    # Attempt to generate analysis
    try:
        logger.info("Requesting analysis from Hugging Face API")
        response = requests.post(
            'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'inputs': prompt,
                'parameters': {
                    'max_new_tokens': 1000,
                    'min_new_tokens': 100,
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'repetition_penalty': 1.1
                }
            }
        )
        
        logger.info(f"Hugging Face Response Status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Hugging Face API Error: {response.text}")
            return {
                "status": "error",
                "message": f"Error analyzing properties. Status code: {response.status_code}",
                "raw_properties": properties[:5]  # Include sample properties in case of error
            }

        result = response.json()
        logger.info("Successfully received analysis from Hugging Face")
        
        if isinstance(result, list):
            generated_text = result[0].get('generated_text', '')
        elif isinstance(result, dict):
            generated_text = result.get('generated_text', '')
        else:
            generated_text = str(result)
        
        # Extract just the analysis part (remove the prompt)
        analysis = generated_text.replace(prompt, '').strip()
        
        if not analysis:
            logger.warning("Empty analysis generated. Using fallback.")
            analysis = "Unable to generate property analysis. Please check the property data and try again."
        
        return {
            "status": "success",
            "analysis": analysis,
            "timestamp": int(time.time()),
            "property_count": len(properties),
            "stats": price_stats
        }

    except Exception as e:
        logger.error(f"Error generating analysis: {str(e)}")
        return {
            "status": "error",
            "message": f"Error analyzing properties: {str(e)}",
            "property_count": len(properties),
            "stats": price_stats
        }


def display_metadata(metadata):
    """
    Display metadata about properties in the feed in a readable format
    
    Args:
        metadata (dict): Metadata from the OPTIONS request
    """
    print("\n" + "=" * 50)
    print("PROPERTY FEED METADATA")
    print("=" * 50)
    
    if not metadata:
        print("No metadata available")
        return
    
    # Print last update and expiration if available
    if "lastUpdate" in metadata:
        print(f"Last Update: {metadata['lastUpdate']}")
    if "expires" in metadata:
        print(f"Expires: {metadata['expires']}")
    
    print("\nAvailable Fields:\n")
    
    # Print fields
    fields = metadata.get("fields", {})
    
    if "cities" in fields:
        print("Cities:")
        for city in sorted(fields["cities"]):
            print(f"  - {city}")
    
    if "counties" in fields:
        print("\nCounties:")
        for county in sorted(fields["counties"]):
            print(f"  - {county}")
    
    if "neighborhoods" in fields:
        print("\nNeighborhoods:")
        for neighborhood in sorted(fields["neighborhoods"]):
            print(f"  - {neighborhood}")
    
    if "status" in fields:
        print("\nProperty Statuses:")
        for status in sorted(fields["status"]):
            print(f"  - {status}")
    
    if "type" in fields:
        print("\nProperty Types:")
        for prop_type in sorted(fields["type"]):
            print(f"  - {prop_type}")
    
    if "features" in fields:
        print("\nFeatures (sample):")
        for feature in sorted(fields["features"])[:10]:  # Show only first 10 to avoid clutter
            print(f"  - {feature}")
        if len(fields["features"]) > 10:
            print(f"  - ... and {len(fields['features']) - 10} more")
    
    if "areaMinor" in fields:
        print("\nMLS Area Minors (sample):")
        for area in sorted(fields["areaMinor"])[:10]:  # Show only first 10 to avoid clutter
            print(f"  - {area}")
        if len(fields["areaMinor"]) > 10:
            print(f"  - ... and {len(fields['areaMinor']) - 10} more")
    
    print("\nHint: Use these values in your search parameters to find properties")
    print("Example: --city \"Houston\" --type \"Residential\"")


def main():
    """Main function to run the script locally"""
    print("\nSimplyRETS Real Estate Analysis Tool with Hugging Face")
    print("=" * 60)
    
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Real Estate Property Analyzer using SimplyRETS API and Hugging Face')
    parser.add_argument('--q', type=str, help='Text search query (e.g. "highlands ranch")')
    parser.add_argument('--city', type=str, help='City to search for properties')
    parser.add_argument('--state', type=str, help='State to search in (e.g. CO for Colorado)')
    parser.add_argument('--county', type=str, help='County to search in')
    parser.add_argument('--minprice', type=int, help='Minimum price')
    parser.add_argument('--maxprice', type=int, help='Maximum price')
    parser.add_argument('--minbeds', type=int, help='Minimum number of bedrooms')
    parser.add_argument('--minbaths', type=int, help='Minimum number of bathrooms')
    parser.add_argument('--type', type=str, help='Property type (e.g. "residential", "rental", "multifamily", "commercial")')
    parser.add_argument('--status', type=str, help='Property status (e.g. "Active", "Pending", "Sold")')
    parser.add_argument('--limit', type=int, default=25, help='Maximum number of properties to retrieve')
    parser.add_argument('--mls', type=str, help='Fetch a specific property by MLS ID')
    parser.add_argument('--metadata', action='store_true', help='Fetch and display property feed metadata')
    parser.add_argument('--vendor', type=str, help='Vendor parameter for metadata (for multiple feeds)')
    parser.add_argument('--output', type=str, default='property_analysis.json', help='Output file for analysis results')
    parser.add_argument('--username', type=str, help='SimplyRETS API username (default: from environment or "simplyrets")')
    parser.add_argument('--password', type=str, help='SimplyRETS API password (default: from environment or "simplyrets")')
    parser.add_argument('--apikey', type=str, help='Hugging Face API key (REQUIRED)')
    parser.add_argument('--skip-ai', action='store_true', help='Skip AI analysis and just collect property data')
    args = parser.parse_args()
    
    # Get API credentials (using demo credentials by default if not provided)
    simplyrets_username = args.username or os.environ.get('SIMPLYRETS_USERNAME', 'simplyrets')
    simplyrets_password = args.password or os.environ.get('SIMPLYRETS_PASSWORD', 'simplyrets')
    huggingface_key = args.apikey or os.environ.get('HUGGINGFACE_KEY')
    
    # Let user know if we're using demo credentials
    if simplyrets_username == 'simplyrets' and simplyrets_password == 'simplyrets':
        print("\nUsing SimplyRETS demo credentials. For access to live MLS data, sign up at https://simplyrets.com/")
        
    # Check for Hugging Face API key if analysis is requested
    if not args.skip_ai and not args.metadata and args.mls is None:
        if not huggingface_key:
            logger.error("Hugging Face API key is required for analysis.")
            print("\nERROR: Hugging Face API key is required for property analysis.")
            print("Please provide your key in one of these ways:")
            print("1. Command line: --apikey YOUR_HF_API_KEY")
            print("2. Environment variable: HUGGINGFACE_KEY")
            print("3. .env file with HUGGINGFACE_KEY=your_key")
            print("\nAlternatively, use --skip-ai to just collect property data without analysis")
            print("or use --metadata to explore available property data.")
            return

    try:
        logger.info(f"Initializing SimplyRETS API client with provided credentials")
        simplyrets_client = SimplyRetsAPI(
            username=simplyrets_username,
            password=simplyrets_password
        )
        
        # Check if we should fetch metadata
        if args.metadata:
            print("\nFetching property feed metadata...")
            metadata = simplyrets_client.get_properties_metadata(vendor=args.vendor)
            
            if metadata:
                display_metadata(metadata)
                
                # Save metadata to file
                with open("property_metadata.json", 'w') as f:
                    json.dump(metadata, f, indent=2)
                print(f"\nMetadata saved to property_metadata.json")
            else:
                print("Failed to retrieve metadata or no metadata available")
                
            # Return if only metadata was requested
            if args.mls is None and args.q is None and args.city is None and args.state is None and args.county is None:
                return
        
        # Check if we're fetching a specific property by MLS ID
        if args.mls:
            print(f"\nFetching property with MLS ID: {args.mls}")
            property_data = simplyrets_client.get_property_by_id(args.mls)
            
            if property_data:
                print("\nProperty Details:")
                print(f"Address: {property_data.get('address', {}).get('full', 'N/A')}")
                print(f"City: {property_data.get('address', {}).get('city', 'N/A')}")
                print(f"Price: ${property_data.get('listPrice', 0):,.0f}")
                print(f"Bedrooms: {property_data.get('property', {}).get('bedrooms', 'N/A')}")
                print(f"Bathrooms: {property_data.get('property', {}).get('bathsFull', 0) + (property_data.get('property', {}).get('bathsHalf', 0) * 0.5)}")
                print(f"Square Feet: {property_data.get('property', {}).get('area', 'N/A')}")
                
                # Save property data to file
                with open(f"property_{args.mls}.json", 'w') as f:
                    json.dump(property_data, f, indent=2)
                print(f"\nFull property details saved to property_{args.mls}.json")
                return
            else:
                print(f"Property with MLS ID {args.mls} not found.")
                return
        
        # Build search parameters for property search
        search_params = {"limit": args.limit}
        
        if args.q:
            search_params["q"] = args.q
        if args.city:
            search_params["cities"] = args.city
        if args.state:
            search_params["states"] = args.state
        if args.county:
            search_params["counties"] = args.county
        if args.minprice:
            search_params["minprice"] = args.minprice
        if args.maxprice:
            search_params["maxprice"] = args.maxprice
        if args.minbeds:
            search_params["minbeds"] = args.minbeds
        if args.minbaths:
            search_params["minbaths"] = args.minbaths
        if args.type:
            search_params["type"] = args.type
        if args.status:
            search_params["status"] = args.status
        
        # Default to a simple query if nothing specific provided
        if (not args.q and not args.city and not args.state and 
            not args.county and not args.minprice and not args.maxprice and 
            not args.minbeds and not args.minbaths and not args.type and 
            not args.status):
            # Just leave default parameters - get any available properties up to the limit
            pass
        
        # Fetch properties
        logger.info(f"Fetching properties with parameters: {search_params}")
        print(f"\nSearching for properties with parameters: {search_params}")
        properties = simplyrets_client.get_properties(search_params)
        
        if not properties:
            logger.warning("No properties found with given search parameters")
            print("\nNo properties found with your search criteria.")
            print("Try running with --metadata to see available cities, property types, etc.")
            return
        
        logger.info(f"Processing {len(properties)} properties for analysis")
        processed_properties = extract_property_data(properties)
        
        # Calculate basic statistics
        try:
            properties_with_price = [p for p in processed_properties if p.get("price") is not None]
            avg_price = sum(p.get("price", 0) or 0 for p in properties_with_price) / len(properties_with_price) if properties_with_price else 0
            
            properties_with_sqft = [p for p in processed_properties if p.get("squareFeet")]
            avg_sqft = sum(p.get("squareFeet", 0) or 0 for p in properties_with_sqft) / len(properties_with_sqft) if properties_with_sqft else 0
            
            # Get additional stats
            min_price = min((p.get("price") for p in properties_with_price), default=0)
            max_price = max((p.get("price") for p in properties_with_price), default=0)
            
            # Find properties with price drops
            price_drops = [p for p in processed_properties if p.get("priceDropPercent") is not None and p.get("priceDropPercent") > 0]
            price_drops.sort(key=lambda p: p.get("priceDropPercent", 0) or 0, reverse=True)
        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            avg_price = 0
            avg_sqft = 0
            min_price = 0
            max_price = 0
            price_drops = []
        
        # Print summary information
        print(f"\nRetrieved {len(properties)} properties")
        print(f"Price Range: ${min_price:,.0f} to ${max_price:,.0f}")
        print(f"Average Price: ${avg_price:,.2f}")
        print(f"Average Square Footage: {avg_sqft:,.0f} sq ft")
        
        # Show locations found
        cities = {}
        for prop in processed_properties:
            city = prop.get('city', 'Unknown')
            if city:
                cities[city] = cities.get(city, 0) + 1
        
        if cities:
            print("\nProperties by location:")
            for city, count in cities.items():
                print(f"  {city}: {count} properties")
        
        if price_drops:
            print(f"\nTop Price Drops:")
            for i, prop in enumerate(price_drops[:3], 1):
                print(f"  {i}. {prop.get('address')} - ${prop.get('price'):,.0f} (↓{prop.get('priceDropPercent')}%)")
        
        # Save processed data to file
        props_file = f"properties_data.json"
        with open(props_file, 'w') as f:
            json.dump(processed_properties, f, indent=2)
        print(f"\nProperty data saved to {props_file}")
        
        # Skip analysis if requested
        if args.skip_ai:
            print("\nSkipping Hugging Face analysis as requested (--skip-ai flag used)")
            print("Property data has been saved to file for your reference.")
            return
            
        # Perform analysis with Hugging Face
        logger.info("Analyzing properties with Hugging Face model")
        print("\nAnalyzing properties with Hugging Face model...")
        analysis_result = analyze_properties_with_huggingface(processed_properties, huggingface_key)
        
        # Save results to file
        output_file = args.output
        with open(output_file, 'w') as f:
            json.dump(analysis_result, f, indent=2)
        
        logger.info(f"Analysis complete. Results saved to {output_file}")
        
        # Print analysis to console
        print("\n" + "=" * 60)
        print("PROPERTY ANALYSIS RESULTS (HUGGING FACE)")
        print("=" * 60)
        if analysis_result.get("status") == "success":
            print(analysis_result.get("analysis"))
        else:
            print(f"Error: {analysis_result.get('message')}")
        print("\n" + "=" * 60)
        print(f"Full results saved to {output_file}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"\nError: {str(e)}")


if __name__ == "__main__":
    main()