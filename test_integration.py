import asyncio
import sys
import os
sys.path.append('.')

from api.news import get_positive_news

async def test_integration():
    print("=== Testing News Scraper with Slider Integration ===")
    
    # Test without slider creation first
    print("\n1. Testing news fetching WITHOUT slider creation:")
    try:
        result = await get_positive_news(create_sliders=False)
        print(f"✅ Status: {result.get('status')}")
        print(f"✅ Articles found: {result.get('count')}")
        print(f"✅ Sliders section present: {'sliders' in result}")
        
        if result.get('articles'):
            first_article = result['articles'][0]
            print(f"✅ First article: {first_article.get('title')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("\n2. Testing news fetching WITH slider creation:")
    try:
        result = await get_positive_news(create_sliders=True)
        print(f"✅ Status: {result.get('status')}")
        print(f"✅ Articles found: {result.get('count')}")
        print(f"✅ Sliders section present: {'sliders' in result}")
        
        if 'sliders' in result:
            sliders = result['sliders']
            print(f"✅ Slider processing message: {sliders.get('message')}")
            print(f"✅ Slider results count: {len(sliders.get('results', []))}")
            
            # Show slider creation attempts
            for i, slider_result in enumerate(sliders.get('results', [])[:2], 1):
                title = slider_result.get('article_title', 'No title')[:50]
                creation = slider_result.get('slider_creation', {})
                if 'error' in creation:
                    print(f"   Slider {i}: {title}... ❌ {creation['error']}")
                else:
                    print(f"   Slider {i}: {title}... ✅ (would create if API was configured)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integration())