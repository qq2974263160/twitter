from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime

class TwitterScraper:
    def __init__(self):
        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式，不显示浏览器
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 初始化浏览器
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def get_user_tweets(self, username, num_tweets=10):
        """获取指定用户的推文"""
        try:
            # 访问用户主页
            self.driver.get(f'https://twitter.com/{username}')
            
            # 等待推文加载
            wait = WebDriverWait(self.driver, 10)
            tweets = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(tweets) < num_tweets:
                # 等待推文元素加载
                article_elements = wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'article[data-testid="tweet"]')))
                
                # 解析推文
                for article in article_elements:
                    if len(tweets) >= num_tweets:
                        break
                        
                    try:
                        # 获取推文文本
                        tweet_text = article.find_element(
                            By.CSS_SELECTOR, 
                            'div[data-testid="tweetText"]'
                        ).text
                        
                        # 获取时间戳
                        time_element = article.find_element(By.TAG_NAME, 'time')
                        timestamp = time_element.get_attribute('datetime')
                        
                        # 获取互动数据
                        stats = {}
                        for stat in ['retweet', 'reply', 'like']:
                            try:
                                stat_element = article.find_element(
                                    By.CSS_SELECTOR, 
                                    f'div[data-testid="{stat}"]'
                                )
                                stats[stat] = stat_element.text
                            except:
                                stats[stat] = '0'
                        
                        tweets.append({
                            'text': tweet_text,
                            'timestamp': timestamp,
                            'stats': stats
                        })
                    except Exception as e:
                        continue
                
                # 滚动页面
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            return tweets
            
        except Exception as e:
            print(f"发生错误: {str(e)}")
            return []
        
    def close(self):
        """关闭浏览器"""
        self.driver.quit()

def main():
    # 创建爬虫实例
    scraper = TwitterScraper()
    
    try:
        # 获取用户输入
        username = input("请输入要爬取的Twitter用户名（不包含@符号）: ")
        num_tweets = int(input("请输入要爬取的推文数量: "))
        
        # 获取推文
        print(f"\n正在爬取 @{username} 的推文...")
        tweets = scraper.get_user_tweets(username, num_tweets)
        
        # 保存结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tweets_{username}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(tweets, f, ensure_ascii=False, indent=2)
        
        print(f"\n成功获取 {len(tweets)} 条推文")
        print(f"结果已保存到文件: {filename}")
        
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 