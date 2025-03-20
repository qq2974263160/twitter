import snscrape.modules.twitter as sntwitter
import pandas as pd
from datetime import datetime

def scrape_user_tweets(username, num_tweets=10):
    """使用snscrape获取用户推文"""
    # 创建查询
    query = f"from:{username}"
    tweets_list = []

    try:
        # 使用TwitterSearchScraper获取推文
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= num_tweets:
                break
                
            tweets_list.append({
                'date': tweet.date,
                'content': tweet.rawContent,
                'likes': tweet.likeCount,
                'retweets': tweet.retweetCount,
                'replies': tweet.replyCount,
                'language': tweet.lang,
                'url': tweet.url
            })

        # 转换为DataFrame
        df = pd.DataFrame(tweets_list)
        
        # 保存结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"tweets_{username}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        
        print(f"\n成功获取 {len(tweets_list)} 条推文")
        print(f"结果已保存到文件: {csv_filename}")
        
        return df

    except Exception as e:
        print(f"发生错误: {str(e)}")
        return None

def main():
    username = input("请输入要爬取的Twitter用户名（不包含@符号）: ")
    num_tweets = int(input("请输入要爬取的推文数量: "))
    
    print(f"\n正在爬取 @{username} 的推文...")
    scrape_user_tweets(username, num_tweets)

if __name__ == "__main__":
    main() 