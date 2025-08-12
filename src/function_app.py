import json
import logging
from typing import Any

import azure.functions as func
import yfinance as yf
from datetime import datetime
import httpx


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }
        

# Define the tool properties for stock price function
tool_properties_get_stockprice_object = [
    ToolProperty("ticker", "string", "The ticker symbol of the company (e.g., AAPL for Apple, TSLA for Tesla).")
]

# Convert the tool properties to JSON
tool_properties_get_stockprice_json = json.dumps([prop.to_dict() for prop in tool_properties_get_stockprice_object])

# Define the tool properties for weather alerts function
tool_properties_get_state_object = [
    ToolProperty("state", "string", "State of weather alerts such as NJ or NY")
]

# Convert the tool properties to JSON
tool_properties_get_state_json = json.dumps([prop.to_dict() for prop in tool_properties_get_state_object])

# Define the tool properties for weather forecast function
tool_properties_get_latlong_object = [
    ToolProperty("latitude", "string", "The latitude of the location for weather"),
    ToolProperty("longitude", "string", "The langitude of the location for weather"),
]
# Convert the tool properties to JSON
tool_properties_get_latlong_json = json.dumps([prop.to_dict() for prop in tool_properties_get_latlong_object])



NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
        Event: {props.get('event', 'Unknown')}
        Area: {props.get('areaDesc', 'Unknown')}
        Severity: {props.get('severity', 'Unknown')}
        Description: {props.get('description', 'No description available')}
        Instructions: {props.get('instruction', 'No specific instructions provided')}
        """

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_stockprice",
    description="Get the stock price of a company using the ticker symbol such as AAPL for Apple.",
    toolProperties=tool_properties_get_stockprice_json,
)
def mcp_get_stockprice(context: str) -> str:
    """
    Get the stock price of a company using the ticker symbol.
    
    Args:
        context: JSON string containing the arguments with ticker symbol
        
    Returns:
        str: JSON string with stock data or error message
    """
    try:
        # Parse the context JSON string to extract the arguments
        mcp_data = json.loads(context)
        print("mcp_data:", mcp_data)
        
        args = mcp_data.get("arguments", {})
        ticker_symbol = args.get("ticker")
        
        # Validate ticker symbol
        if not ticker_symbol:
            return json.dumps({
                "error": "No ticker symbol provided. Please provide a ticker symbol like TSLA, AAPL, etc."
            })
        
        ticker_symbol = ticker_symbol.upper().strip()
        print(f"Fetching stock data for: {ticker_symbol}")
        
        # Create a Ticker object and fetch data
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        # Check if we got valid data
        if not info or 'currentPrice' not in info:
            return json.dumps({
                "error": f"Unable to fetch stock data for ticker symbol: {ticker_symbol}. Please check if the symbol is valid."
            })
        
        # Prepare the response data
        date = datetime.today().strftime('%Y-%m-%d')
        
        result = {
            "symbol": ticker_symbol,
            "date": date,
            "current_price": info.get('currentPrice', 'N/A'),
            "day_low": info.get('dayLow', 'N/A'),
            "day_high": info.get('dayHigh', 'N/A'),
            "opening_price": info.get('open', 'N/A'),
            "previous_close": info.get('previousClose', 'N/A'),
            "market_cap": info.get('marketCap', 'N/A'),
            "company_name": info.get('longName', ticker_symbol),
            "link": f"https://finance.yahoo.com/quote/{ticker_symbol}/"
        }
        
        print(f"Successfully fetched stock data for {ticker_symbol}")
        return json.dumps(result, indent=2)
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON context provided: {str(e)}"
        print(error_msg)
        return json.dumps({"error": error_msg})
        
    except Exception as e:
        error_msg = f"Error fetching stock data for {ticker_symbol if 'ticker_symbol' in locals() else 'unknown ticker'}: {str(e)}"
        print(error_msg)
        return json.dumps({"error": error_msg})   
    
    
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weatheralerts",
    description="Get the weather alerts of the state",
    toolProperties=tool_properties_get_state_json,
)
def mcp_get_weatheralerts(context: str) -> None:
    
    mcp_data = json.loads(context)
    args = mcp_data.get("arguments", {})
    
    state = args.get("state")
     
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    
    #data = await make_nws_request(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    with httpx.Client() as client:
        try:
            response = client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
        except Exception:
            data = None

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)    

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weatherforecast",
    description="Get the weather forecast of a place based on latitute and logitude",
    toolProperties=tool_properties_get_latlong_json,
)
def mcp_get_weatherforecast(context: str) -> None:
    
    mcp_data = json.loads(context)
    args = mcp_data.get("arguments", {})
     
    latitude = args.get("latitude")
    longitude = args.get("longitude")
    
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    #points_data = await make_nws_request(points_url)
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    with httpx.Client() as client:
        try:
            response = client.get(points_url, headers=headers, timeout=30.0)
            response.raise_for_status()
            points_data =  response.json()
        except Exception:
            points_data= None
    
    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    #forecast_data = await make_nws_request(forecast_url)
        
    with httpx.Client() as client:
        try:
            response = client.get(forecast_url, headers=headers, timeout=30.0)
            response.raise_for_status()
            forecast_data =  response.json()
        except Exception:
            forecast_data= None

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
            {period['name']}:
            Temperature: {period['temperature']}°{period['temperatureUnit']}
            Wind: {period['windSpeed']} {period['windDirection']}
            Forecast: {period['detailedForecast']}
            """
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)
