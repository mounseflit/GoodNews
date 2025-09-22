import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.news import app, get_positive_news

async def test_news_with_sliders():
    print("Testing news fetching with slider creation...")
    try:
        # Test with slider creation enabled
        result = await get_positive_news(create_sliders=True)
        print("Success!")
        print("Result type:", type(result))
        print("Status:", result.get("status"))
        print("Article count:", result.get("count"))
        
        if "sliders" in result:
            print("Slider creation results:")
            slider_results = result["sliders"]
            print("Message:", slider_results.get("message"))
            print("Results count:", len(slider_results.get("results", [])))
            
            for i, slider_result in enumerate(slider_results.get("results", []), 1):
                print(f"  Slider {i}: {slider_result.get('article_title')}")
                creation_result = slider_result.get('slider_creation', {})
                if creation_result.get('success'):
                    print(f"    ✅ Created successfully")
                else:
                    print(f"    ❌ Failed: {creation_result.get('error', 'Unknown error')}")
        else:
            print("No slider creation attempted")
            
        return result
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

async def test_news_without_sliders():
    print("\nTesting news fetching without slider creation...")
    try:
        result = await get_positive_news(create_sliders=False)
        print("Success!")
        print("Status:", result.get("status"))
        print("Article count:", result.get("count"))
        print("Sliders key present:", "sliders" in result)
        return result
    except Exception as e:
        print("Error:", str(e))
        return {"error": str(e)}

if __name__ == "__main__":
    print("=== Testing Good News Scraper with Slider Integration ===")
    
    # Test with sliders
    result1 = asyncio.run(test_news_with_sliders())
    
    # Test without sliders
    result2 = asyncio.run(test_news_without_sliders())