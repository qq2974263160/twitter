import os
import time
import json
import logging
import tweepy
import urllib3
import ssl
from dotenv import load_dotenv
from datetime import datetime, timedelta
from requests.exceptions import SSLError
from urllib3.exceptions import SSLError as URLLibSSLError
import logging.handlers
import colorama
from colorama import Fore, Style

# 加载配置
def load_config():
    """加载配置文件"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("配置文件 config.json 不存在")
        raise
    except json.JSONDecodeError:
        logger.error("配置文件格式错误")
        raise
    except Exception as e:
        logger.error(f"加载配置文件时发生错误: {str(e)}")
        raise

# 配置日志
def setup_logging():
    """配置日志系统"""
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 只保留主日志和控制台输出
    handlers = [
        logging.FileHandler('twitter_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
    
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = handlers
    
    return logger

# 初始化日志系统
logger = setup_logging()

# 加载环境变量和配置
load_dotenv()
CONFIG = load_config()

# 从配置文件获取常量
MIN_RESULTS_PER_REQUEST = CONFIG['min_results_per_request']  # 每次请求最少结果数
MAX_RESULTS_PER_REQUEST = 100   # Twitter API支持最大100条
RATE_LIMIT_WINDOW = CONFIG['rate_limit_window']  # 速率限制窗口(秒)
TWITTER_ACCOUNTS = CONFIG['twitter_accounts']     # Twitter账号配置
EXPORT_FORMATS = ['json', 'csv']            # 支持的导出格式

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 初始化colorama
colorama.init()

class RetryableTwitterClient:
    def __init__(self):
        self.clients = []
        self.current_index = 0
        self.initialize_clients()

    def initialize_clients(self):
        """初始化多个Twitter API客户端"""
        for account in TWITTER_ACCOUNTS:
            try:
                client = tweepy.Client(
                    bearer_token=account['bearer_token'],
                    consumer_key=account['api_key'],
                    consumer_secret=account['api_key_secret'],
                    access_token=account['access_token'],
                    access_token_secret=account['access_token_secret']
                )
                self.clients.append({
                    'name': account['name'],
                    'client': client,
                    'is_active': True
                })
            except Exception as e:
                logger.error(f"客户端 {account['name']} 初始化失败: {str(e)}")

    def make_request(self, func, endpoint, *args, **kwargs):
        """
        发送API请求并处理速率限制
        :param func: API调用函数
        :param endpoint: API端点名称
        :return: API响应
        """
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            current_client = self.clients[self.current_index]
            
            try:
                response = func(current_client['client'])
                
                if hasattr(response, 'response') and hasattr(response.response, 'headers'):
                    headers = response.response.headers
                    limit = int(headers.get('x-rate-limit-limit', 0))
                    remaining = int(headers.get('x-rate-limit-remaining', 0))
                    reset_time = int(headers.get('x-rate-limit-reset', 0))
                    
                    logger.info(f"API限制信息 - 限制: {limit}, 剩余: {remaining}, 重置时间: {reset_time}")
                    
                    if limit > 0 and remaining < limit * 0.2:
                        logger.warning(f"API请求次数即将用完，剩余: {remaining}/{limit}")
                
                return response
                
            except tweepy.TooManyRequests as e:
                retries += 1
                
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
                    current_time = int(time.time())
                    
                    if reset_time > current_time:
                        wait_time = reset_time - current_time
                        logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试")
                        time.sleep(wait_time)
                    else:
                        wait_time = min(300, (2 ** retries) * 5)
                        logger.warning(f"未获取到重置时间，等待 {wait_time} 秒后重试")
                        time.sleep(wait_time)
                else:
                    wait_time = min(300, (2 ** retries) * 5)
                    logger.warning(f"无法获取速率限制信息，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                
                if retries < max_retries:
                    self.current_index = (self.current_index + 1) % len(self.clients)
                    logger.info(f"切换到下一个客户端: {self.clients[self.current_index]['name']}")
                
            except Exception as e:
                retries += 1
                logger.error(f"请求失败: {str(e)}")
                if retries >= max_retries:
                    raise
                time.sleep(5)
        
        raise Exception(f"达到最大重试次数 ({max_retries})")

def get_tweet_params():
    """返回推文API请求参数"""
    return {
        'tweet_fields': [
            'created_at',
            'text',
            'conversation_id'
        ],
        'max_results': MAX_RESULTS_PER_REQUEST
    }

def handle_rate_limit(e, retry_count):
    """
    处理API速率限制
    :param e: 异常对象
    :param retry_count: 重试次数
    :return: 等待时间
    """
    if hasattr(e, 'response') and hasattr(e.response, 'headers'):
        reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
        current_time = int(time.time())
        
        if reset_time > current_time:
            wait_time = reset_time - current_time
            logger.warning(f"遇到API速率限制，等待 {wait_time} 秒后继续")
            return wait_time
        else:
            logger.warning("API速率限制已过期，继续获取")
            return 0
    else:
        logger.warning("无法获取API重置时间，使用默认等待时间")
        return 300  # 等待5分钟

def get_tweet_replies(client, tweet_id):
    """
    获取推文的评论
    :param client: Twitter客户端
    :param tweet_id: 推文ID
    :return: 评论列表
    """
    try:
        params = {
            'query': f'conversation_id:{tweet_id}',
            'tweet_fields': ['created_at', 'text', 'author_id'],
            'max_results': 100
        }
        
        replies = client.make_request(
            lambda client: client.search_recent_tweets(**params),
            'search_recent_tweets'
        )
        
        if not replies or not hasattr(replies, 'data'):
            return []
            
        return replies.data
    except Exception as e:
        logger.error(f"获取推文评论失败: {str(e)}")
        return []

def get_tweet_data(tweet):
    """
    提取推文的核心数据
    :param tweet: 推文对象
    :return: 包含ID、时间、内容和评论的字典
    """
    return {
        'id': tweet.id,
        'created_at': tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else '',
        'text': tweet.text,
        'replies': getattr(tweet, 'replies', [])
    }

def get_tweets_with_pagination(client, get_tweets_func, params):
    """
    分页获取推文及其评论
    :param client: Twitter客户端
    :param get_tweets_func: 获取推文的函数
    :param params: API参数
    :return: 推文列表
    """
    tweets_data = []
    pagination_token = None
    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            if pagination_token:
                params['pagination_token'] = pagination_token
            
            logger.info(f"正在获取 {params['max_results']} 条推文")
            tweets = client.make_request(get_tweets_func, get_tweets_func.__name__, **params)

            if not tweets or not hasattr(tweets, 'data') or not tweets.data:
                logger.warning("未获取到推文数据")
                break

            for tweet in tweets.data:
                tweet.replies = get_tweet_replies(client, tweet.id)
                print(f"已获取推文 {tweet.id} 的 {len(tweet.replies)} 条评论")

            tweets_data.extend(tweets.data)
            print(f"已获取 {len(tweets_data)} 条推文")

            if hasattr(tweets, 'meta') and tweets.meta and tweets.meta.get('next_token'):
                pagination_token = tweets.meta['next_token']
                time.sleep(2)
            else:
                break

        except tweepy.TooManyRequests as e:
            wait_time = handle_rate_limit(e, retry_count)
            if wait_time > 0:
                time.sleep(wait_time)
            retry_count += 1
            continue
            
        except Exception as e:
            logger.error(f"获取推文时发生错误: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                break
            time.sleep(5)

    return tweets_data

def get_user_tweets(client, username):
    """
    获取指定用户的推文
    :param client: Twitter客户端
    :param username: 用户名
    :return: 推文列表
    """
    try:
        print(f"\n正在获取用户 {username} 的推文...")
        
        try:
            logger.info(f"正在获取用户 {username} 的信息")
            user = client.make_request(
                lambda client: client.get_user(username=username),
                'get_user'
            )
            
            if not user or not user.data:
                logger.warning(f"未找到用户: {username}")
                return []
            
            user_id = user.data.id
            logger.info(f"找到用户ID: {user_id}")
        except Exception as e:
            logger.error(f"获取用户信息时发生错误: {str(e)}")
            return []

        tweet_params = get_tweet_params()
        tweet_params['id'] = user_id

        tweets_data = get_tweets_with_pagination(client, client.get_users_tweets, tweet_params)
        print(f"\n成功获取 {len(tweets_data)} 条推文")
        return tweets_data
        
    except Exception as e:
        print(f"\n获取推文过程中发生错误: {str(e)}")
        return []
    finally:
        logger.info(f"完成获取用户 {username} 的推文")

def get_home_timeline(client):
    """
    获取首页时间线推文
    :param client: Twitter客户端
    :return: 推文列表
    """
    try:
        print(f"\n正在获取首页时间线推文...")
        tweet_params = get_tweet_params()
        tweets_data = get_tweets_with_pagination(client, client.get_home_timeline, tweet_params)
        print(f"\n成功获取 {len(tweets_data)} 条推文")
        return tweets_data
        
    except Exception as e:
        print(f"\n获取推文过程中发生错误: {str(e)}")
        return []
    finally:
        logger.info("完成获取首页时间线推文")

def export_tweets(tweets, format_type=None, filename=None):
    """
    导出推文数据到文件
    :param tweets: 推文列表
    :param format_type: 导出格式(json/csv)
    :param filename: 文件名
    :return: 导出文件路径
    """
    if not tweets:
        print("没有可导出的推文数据")
        return None
        
    try:
        if not format_type:
            print("\n可用的导出格式：")
            for i, fmt in enumerate(EXPORT_FORMATS, 1):
                print(f"{i}. {fmt}")

            try:
                format_choice = int(input("\n请选择导出格式（输入序号）: ").strip())
                if 1 <= format_choice <= len(EXPORT_FORMATS):
                    format_type = EXPORT_FORMATS[format_choice - 1]
                else:
                    print("无效的选择")
                    return None
            except ValueError:
                print("无效的输入")
                return None
            
        if format_type not in EXPORT_FORMATS:
            print(f"不支持的导出格式: {format_type}")
            return None
            
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tweets_{timestamp}.{format_type}"
            
        print(f"\n正在导出 {len(tweets)} 条推文到 {filename}...")
        
        if format_type == 'json':
            data = [get_tweet_data(tweet) for tweet in tweets]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        elif format_type == 'csv':
            import csv
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['推文ID', '发布时间', '内容', '评论数', '评论内容'])
                
                for tweet in tweets:
                    data = get_tweet_data(tweet)
                    replies = data['replies']
                    reply_texts = '\n'.join([reply.text for reply in replies])
                    writer.writerow([
                        data['id'],
                        data['created_at'],
                        data['text'],
                        len(replies),
                        reply_texts
                    ])
                        
        print(f"\n数据已成功导出到: {filename}")
        return filename
        
    except Exception as e:
        print(f"\n导出数据时出错: {str(e)}")
        logger.error(f"导出数据时出错: {str(e)}")
        return None

def handle_get_tweets(twitter_client):
    """处理用户推文获取请求"""
    try:
        target_username = input("请输入要爬取的Twitter用户名（不包含@符号）: ").strip()
        if not target_username:
            print("用户名不能为空")
            return

        tweets = get_user_tweets(twitter_client, target_username)
        if tweets:
            export_tweets(tweets)

    except Exception as e:
        print(f"操作失败: {str(e)}")
        logger.error(f"获取推文操作失败: {str(e)}", exc_info=True)

def handle_get_home_timeline(twitter_client):
    """处理首页时间线推文获取请求"""
    try:
        tweets = get_home_timeline(twitter_client)
        if tweets:
            export_tweets(tweets)
    except Exception as e:
        print(f"操作失败: {str(e)}")
        logger.error(f"获取首页时间线推文操作失败: {str(e)}", exc_info=True)

def main():
    """程序入口，提供交互式菜单"""
    try:
        client = RetryableTwitterClient()
        if not client.clients:
            print("API客户端初始化失败")
            return

        while True:
            print("\n=== Twitter爬虫工具 ===")
            print("1. 获取用户推文")
            print("2. 获取首页时间线推文")
            print("q. 退出")
            
            choice = input("\n请选择: ").strip()
            
            if choice == 'q':
                break
            elif choice == '1':
                handle_get_tweets(client)
            elif choice == '2':
                handle_get_home_timeline(client)
            else:
                print("无效的选择")

    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"程序错误: {str(e)}")
    finally:
        colorama.deinit()

if __name__ == "__main__":
    main() 