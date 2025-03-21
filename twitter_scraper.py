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
from tqdm import tqdm
import colorama
from colorama import Fore, Style

# 加载配置
def load_config():
    """
    加载JSON格式的配置文件
    返回: 配置字典
    异常: 文件不存在、JSON格式错误等
    """
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
    """
    配置日志系统，包括：
    1. 主日志文件(twitter_scraper.log)
    2. 错误日志文件(twitter_scraper.error.log)
    3. 性能日志文件(twitter_scraper.perf.log)
    4. 控制台输出
    返回: 根日志记录器
    """
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建文件处理器(带日志轮转)
    file_handler = logging.handlers.RotatingFileHandler(
        'twitter_scraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 创建错误日志处理器
    error_handler = logging.handlers.RotatingFileHandler(
        'twitter_scraper.error.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除现有的处理器
    root_logger.handlers = []

    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_handler)

    # 创建性能日志记录器
    perf_logger = logging.getLogger('performance')
    perf_handler = logging.handlers.RotatingFileHandler(
        'twitter_scraper.perf.log',
        maxBytes=5*1024*1024,
        backupCount=2,
        encoding='utf-8'
    )
    perf_handler.setFormatter(formatter)
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False  # 不传播到父记录器

    return root_logger

# 初始化日志系统
logger = setup_logging()
perf_logger = logging.getLogger('performance')

# 加载环境变量和配置
load_dotenv()
CONFIG = load_config()

# 从配置文件获取常量
CACHE_FILE = CONFIG['cache_file']                # 缓存文件路径
CACHE_EXPIRE_HOURS = CONFIG['cache_expire_hours'] # 缓存过期时间(小时)
MAX_CACHE_SIZE = CONFIG['max_cache_size']        # 最大缓存大小
MIN_RESULTS_PER_REQUEST = CONFIG['min_results_per_request']  # 每次请求最少结果数
MAX_RESULTS_PER_REQUEST = 100   # Twitter API支持最大100条
RATE_LIMIT_WINDOW = CONFIG['rate_limit_window']  # 速率限制窗口(秒)
TWITTER_ACCOUNTS = CONFIG['twitter_accounts']     # Twitter账号配置

# Twitter API认证信息配置
TWITTER_ACCOUNTS = [
    {
        'name': 'account1',
        'bearer_token': 'AAAAAAAAAAAAAAAAAAAAAGo40AEAAAAArfHfelHEmRLeuog82WT4l8Fo7i8%3DaxDQ1xGblrstL9nN1ziJjqpIOOD0R0XeS8GixJjwSkMnaHwdnE',
        'api_key': '2bcxapYbbGz6aAjk62vfce6wX',
        'api_key_secret': 'lJGQcqk00x5fAjH6TDuR98BDs04HKjVp5brp543LQ4lSD85ELf',
        'access_token': '1902562784367595520-Y4AA4LtXzT6vPYBak02R9j7OkfFUt0',
        'access_token_secret': 'DJbWKGT1uItsFa7tNpkBaBNwnGR5HCWksBEvdARgU6PHZ'
    },
    {
        'name': 'account2',
        'bearer_token': 'AAAAAAAAAAAAAAAAAAAAAG890AEAAAAAbZe%2B4KRyx2GzE%2FJ4W%2BWgLQL9CVc%3D37DJbvfLfpSIUIZBSUnMFCieQIGpt34zxyOlrRKsMD49DX3fwY',
        'api_key': 'NTfK0nzyURltHIZi9hhbOyYdF',
        'api_key_secret': '3uz43PzgjvHJqCrbpPlwJsJgcbI6Cy9a5sQfzPjKWDqo0mxSiy',
        'access_token': '1836805399472947200-J8hQe0KCT9T0dF20wSCmMTjA0Yq1ng',
        'access_token_secret': 'hNdBu6AtRzKgQ4WwI2O9nfmoDqemVGdHbh1hNWIDwmzFW'
    }
]

# 全局配置常量
CACHE_FILE = 'twitter_cache.json'           # 缓存文件名
CACHE_EXPIRE_HOURS = 24                     # 缓存过期时间
MAX_CACHE_SIZE = 100 * 1024 * 1024         # 最大缓存大小(100MB)
MIN_RESULTS_PER_REQUEST = 5                 # 单次请求最少结果数
MAX_RESULTS_PER_REQUEST = 10                # 单次请求最大结果数
RATE_LIMIT_WINDOW = 900                     # 速率限制窗口(15分钟)
EXPORT_FORMATS = ['json', 'csv']            # 支持的导出格式

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 初始化colorama
colorama.init()

class ProgressBar:
    """
    进度条类，用于显示操作进度
    基于tqdm库实现，提供简单的进度显示界面
    """
    def __init__(self, total, desc="进度"):
        """
        初始化进度条
        :param total: 总任务数
        :param desc: 进度条描述文字
        """
        self.pbar = tqdm(
            total=total,
            desc=desc,
            unit="条",
            ncols=80,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        )

    def update(self, n=1):
        """更新进度"""
        self.pbar.update(n)

    def close(self):
        """关闭进度条"""
        self.pbar.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()

# 终端颜色输出函数
def print_colored(text, color=Fore.WHITE, style=Style.NORMAL):
    """
    打印彩色文本
    :param text: 要打印的文本
    :param color: 文本颜色
    :param style: 文本样式
    """
    print(f"{style}{color}{text}{Style.RESET_ALL}")

def print_success(text):
    """打印成功信息（绿色）"""
    print_colored(text, Fore.GREEN, Style.BRIGHT)

def print_error(text):
    """打印错误信息（红色）"""
    print_colored(text, Fore.RED, Style.BRIGHT)

def print_warning(text):
    """打印警告信息（黄色）"""
    print_colored(text, Fore.YELLOW, Style.BRIGHT)

def print_info(text):
    """打印普通信息（青色）"""
    print_colored(text, Fore.CYAN, Style.NORMAL)

class RateLimitTracker:
    """
    API速率限制追踪器
    用于管理Twitter API的请求限制，避免超出配额
    包含请求计数、等待时间计算和智能退避策略
    """
    def __init__(self):
        # 初始化每个端点的请求记录
        self.requests = {
            'get_user': [],         # 获取用户信息的请求记录
            'get_users_tweets': []  # 获取用户推文的请求记录
        }
        self.window_size = RATE_LIMIT_WINDOW  # 时间窗口大小
        self.endpoint_limits = {
            'get_user': {'limit': 900, 'window': 900},        # 900次/15分钟
            'get_users_tweets': {'limit': 180, 'window': 900} # 180次/15分钟
        }
        self.min_interval = 3.0     # 最小请求间隔(秒)
        self.backoff_factor = 1.5   # 退避因子

    def add_request(self, endpoint):
        """
        记录新的API请求
        :param endpoint: API端点名称
        """
        current_time = time.time()
        if endpoint not in self.requests:
            self.requests[endpoint] = []
        self.requests[endpoint].append(current_time)
        self._cleanup_old_requests(endpoint, current_time)

    def _cleanup_old_requests(self, endpoint, current_time):
        """
        清理超出时间窗口的旧请求记录
        :param endpoint: API端点名称
        :param current_time: 当前时间戳
        """
        if endpoint not in self.endpoint_limits:
            return
        window = self.endpoint_limits[endpoint]['window']
        cutoff_time = current_time - window
        self.requests[endpoint] = [t for t in self.requests[endpoint] if t > cutoff_time]

    def get_remaining_requests(self, endpoint):
        """
        获取指定端点的剩余请求配额
        :param endpoint: API端点名称
        :return: 剩余可用请求数
        """
        if endpoint not in self.endpoint_limits:
            return 999  # 对于未知端点，返回一个大数
        self._cleanup_old_requests(endpoint, time.time())
        limit = self.endpoint_limits[endpoint]['limit']
        count = len(self.requests.get(endpoint, []))
        remaining = max(0, limit - count)
        
        # 当配额较低时记录警告
        if remaining < limit * 0.2:  # 剩余配额低于20%
            logger.warning(f"{endpoint} 剩余配额较低: {remaining}/{limit}")
        
        return remaining

    def should_wait(self, endpoint):
        """
        检查是否需要等待后再发送请求
        :param endpoint: API端点名称
        :return: (是否需要等待, 需要等待的时间)
        """
        current_time = time.time()
        
        # 确保端点存在
        if endpoint not in self.requests:
            self.requests[endpoint] = []
        
        # 获取请求记录
        requests = self.requests[endpoint]
        
        # 检查最小间隔
        if requests:
            last_request = max(requests)
            time_since_last = current_time - last_request
            if time_since_last < self.min_interval:
                return True, self.min_interval - time_since_last

        # 检查配额
        remaining = self.get_remaining_requests(endpoint)
        if remaining <= 5:  # 当剩余配额较低时增加等待时间
            wait_time = self._get_wait_time(endpoint)
            # 根据剩余配额动态调整等待时间
            if remaining <= 2:
                wait_time *= self.backoff_factor
            return True, wait_time

        # 根据请求频率动态调整间隔
        if len(requests) >= 5:  # 如果有足够的请求历史
            recent_requests = sorted(requests[-5:])  # 获取最近5个请求
            avg_interval = (recent_requests[-1] - recent_requests[0]) / 4  # 计算平均间隔
            if avg_interval < self.min_interval:
                return True, self.min_interval * self.backoff_factor

        return False, 0

    def _get_wait_time(self, endpoint):
        """
        计算需要等待的时间
        :param endpoint: API端点名称
        :return: 需要等待的秒数
        """
        if endpoint not in self.requests or not self.requests[endpoint]:
            return 0
        window = self.endpoint_limits.get(endpoint, {}).get('window', self.window_size)
        oldest_request = min(self.requests[endpoint])
        wait_time = max(0, (oldest_request + window) - time.time())
        
        # 添加动态缓冲时间
        buffer_time = min(30, wait_time * 0.1)  # 最多额外等待30秒
        return wait_time + buffer_time

class RetryableTwitterClient:
    """
    可重试的Twitter客户端
    提供自动重试、错误处理和负载均衡功能的Twitter API客户端
    支持多账号轮换和智能请求限制
    """
    def __init__(self, max_retries=3, retry_delay=2):
        """
        初始化Twitter客户端
        :param max_retries: 最大重试次数
        :param retry_delay: 重试基础延迟时间(秒)
        """
        self.clients = []              # 客户端列表
        self.current_client_index = 0  # 当前使用的客户端索引
        self.rate_limiter = RateLimitTracker()  # 速率限制追踪器
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.initialize_all_clients()
        # 错误计数器
        self.error_counts = {
            'network': 0,    # 网络错误
            'auth': 0,       # 认证错误
            'rate_limit': 0, # 速率限制错误
            'other': 0       # 其他错误
        }
        # 不同类型错误的退避时间
        self.backoff_times = {
            'network': 10,    # 网络错误等待时间
            'auth': 15,       # 认证错误等待时间
            'rate_limit': 30, # 速率限制等待时间
            'other': 5        # 其他错误等待时间
        }

    def initialize_all_clients(self):
        """
        初始化所有Twitter API客户端
        从环境变量加载认证信息并创建客户端实例
        """
        for i in range(1, 3):  # 支持两个账号
            try:
                client = tweepy.Client(
                    bearer_token=os.getenv(f'TWITTER_BEARER_TOKEN_{i}'),
                    consumer_key=os.getenv(f'TWITTER_API_KEY_{i}'),
                    consumer_secret=os.getenv(f'TWITTER_API_KEY_SECRET_{i}'),
                    access_token=os.getenv(f'TWITTER_ACCESS_TOKEN_{i}'),
                    access_token_secret=os.getenv(f'TWITTER_ACCESS_TOKEN_SECRET_{i}'),
                    wait_on_rate_limit=False
                )
                self.clients.append({
                    'name': f'account{i}',
                    'client': client,
                    'is_active': True
                })
                logger.info(f"Twitter API客户端 account{i} 初始化成功")
            except Exception as e:
                logger.error(f"API客户端 account{i} 初始化错误: {str(e)}")

    def get_next_active_client(self):
        """
        获取下一个可用的客户端
        :return: 可用的客户端配置，如果没有可用客户端则返回None
        """
        original_index = self.current_client_index
        while True:
            self.current_client_index = (self.current_client_index + 1) % len(self.clients)
            if self.clients[self.current_client_index]['is_active']:
                return self.clients[self.current_client_index]
            if self.current_client_index == original_index:
                return None

    def _get_error_type(self, error):
        """
        识别错误类型
        :param error: 捕获的异常
        :return: 错误类型字符串
        """
        if isinstance(error, tweepy.errors.TooManyRequests):
            return 'rate_limit'
        elif isinstance(error, (ssl.SSLError, SSLError, URLLibSSLError)):
            return 'network'
        elif isinstance(error, tweepy.errors.Unauthorized):
            return 'auth'
        elif isinstance(error, tweepy.errors.TweepyException):
            if '429' in str(error):  # 检查是否是速率限制错误
                return 'rate_limit'
            return 'network'
        return 'other'

    def _get_wait_time(self, error_type, retry_count):
        """
        计算智能等待时间
        :param error_type: 错误类型
        :param retry_count: 当前重试次数
        :return: 需要等待的秒数
        """
        base_time = self.backoff_times[error_type]
        if error_type == 'rate_limit':
            # 对于速率限制错误，使用更激进的退避策略
            wait_time = base_time * (3 ** retry_count)  # 使用3作为基数而不是2
            return min(wait_time, 900)  # 最大等待15分钟
        else:
            # 其他错误使用普通的指数退避
            wait_time = base_time * (2 ** retry_count)
            return min(wait_time, 300)  # 最大等待5分钟

    def make_request(self, func, endpoint, *args, **kwargs):
        """
        执行API请求并处理错误
        :param func: 要执行的API函数
        :param endpoint: API端点名称
        :param args: 传递给API函数的位置参数
        :param kwargs: 传递给API函数的关键字参数
        :return: API响应
        :raises: 达到最大重试次数后的最后一个异常
        """
        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            current_client = self.clients[self.current_client_index]
            if not current_client['is_active']:
                next_client = self.get_next_active_client()
                if not next_client:
                    logger.error("所有API客户端都不可用")
                    raise Exception("所有API客户端都不可用")
                current_client = next_client
                logger.info(f"切换到API客户端: {current_client['name']}")

            try:
                # 检查速率限制
                should_wait, wait_time = self.rate_limiter.should_wait(endpoint)
                if should_wait:
                    logger.info(f"速率限制: 等待 {wait_time:.1f} 秒")
                    time.sleep(wait_time)

                # 记录请求
                self.rate_limiter.add_request(endpoint)
                
                # 执行请求
                response = func(current_client['client'])
                if response is None:
                    raise Exception("API返回空响应")
                
                # 成功后重置该类型的错误计数
                error_type = self._get_error_type(last_error) if last_error else 'other'
                self.error_counts[error_type] = 0
                
                return response
                
            except Exception as e:
                error_type = self._get_error_type(e)
                self.error_counts[error_type] += 1
                wait_time = self._get_wait_time(error_type, retries)
                
                if error_type == 'rate_limit':
                    logger.warning(
                        f"{endpoint} 遇到速率限制, "
                        f"第 {retries + 1}/{self.max_retries} 次重试, "
                        f"等待 {wait_time} 秒后重试"
                    )
                    # 当遇到速率限制时，将当前客户端标记为不活跃并切换到下一个
                    current_client['is_active'] = False
                    next_client = self.get_next_active_client()
                    if next_client:
                        logger.info(f"由于速率限制，切换到客户端: {next_client['name']}")
                        continue
                else:
                    logger.warning(
                        f"{endpoint} 请求失败 ({error_type}), "
                        f"第 {retries + 1}/{self.max_retries} 次重试, "
                        f"等待 {wait_time} 秒. 错误: {str(e)}"
                    )
                
                # 特殊错误处理
                if error_type == 'auth':
                    logger.error(f"客户端 {current_client['name']} 认证失败")
                    current_client['is_active'] = False
                    next_client = self.get_next_active_client()
                    if next_client:
                        logger.info(f"由于认证失败，切换到客户端: {next_client['name']}")
                        continue
                    break
                elif self.error_counts[error_type] >= 10:
                    logger.error(f"{error_type} 错误次数过多,请检查系统状态")
                    break
                
                time.sleep(wait_time)
                retries += 1
                last_error = e

        # 达到最大重试次数
        if last_error:
            error_type = self._get_error_type(last_error)
            if error_type == 'rate_limit':
                logger.error(f"{endpoint} 所有客户端都达到API速率限制，请等待一段时间后再试")
            else:
                logger.error(
                    f"{endpoint} 达到最大重试次数 ({self.max_retries}), "
                    f"最后一次错误: {str(last_error)}"
                )
            raise last_error

    def _reset_inactive_clients(self):
        """定期检查并重置被禁用的客户端"""
        current_time = time.time()
        for client in self.clients:
            if not client['is_active'] and current_time - client.get('deactivated_time', 0) > 900:
                client['is_active'] = True

def tweet_to_dict(tweet, includes=None):
    """
    将Tweet对象转换为可序列化的字典
    :param tweet: Tweet对象
    :param includes: 包含媒体、引用推文等额外信息的字典
    :return: 包含推文信息的字典
    """
    try:
        tweet_dict = {
            'id': str(tweet.id),
            'created_at': tweet.created_at.isoformat(),
            'text': format_tweet_text(tweet),
            'metrics': {
                'like_count': tweet.public_metrics.get('like_count', 0),
                'retweet_count': tweet.public_metrics.get('retweet_count', 0),
                'reply_count': tweet.public_metrics.get('reply_count', 0),
                'quote_count': tweet.public_metrics.get('quote_count', 0)
            },
            'urls': [],
            'media': [],
            'referenced_tweets': []
        }

        # 处理URLs
        if hasattr(tweet, 'entities') and 'urls' in tweet.entities:
            for url in tweet.entities['urls']:
                url_info = {
                    'url': url.get('url'),
                    'expanded_url': url.get('expanded_url'),
                    'display_url': url.get('display_url'),
                    'title': url.get('title', ''),
                    'description': url.get('description', '')
                }
                tweet_dict['urls'].append(url_info)

        # 处理媒体附件
        if includes and 'media' in includes:
            media_dict = {m['media_key']: m for m in includes['media']}
            if hasattr(tweet, 'attachments') and 'media_keys' in tweet.attachments:
                for media_key in tweet.attachments['media_keys']:
                    if media_key in media_dict:
                        media = media_dict[media_key]
                        media_info = {
                            'type': media.get('type'),
                            'url': media.get('url') or media.get('preview_image_url'),
                            'height': media.get('height'),
                            'width': media.get('width'),
                            'alt_text': media.get('alt_text')
                        }
                        tweet_dict['media'].append(media_info)

        # 处理引用推文
        if hasattr(tweet, 'referenced_tweets') and includes and 'tweets' in includes:
            ref_tweets_dict = {t['id']: t for t in includes['tweets']}
            for ref in tweet.referenced_tweets:
                if ref['id'] in ref_tweets_dict:
                    ref_tweet = ref_tweets_dict[ref['id']]
                    ref_info = {
                        'type': ref['type'],
                        'id': ref['id'],
                        'text': ref_tweet.get('text', ''),
                        'author_id': ref_tweet.get('author_id')
                    }
                    tweet_dict['referenced_tweets'].append(ref_info)

        return tweet_dict
    except Exception as e:
        logger.error(
            f"转换推文失败: {str(e)}", 
            extra={
                'tweet_id': getattr(tweet, 'id', 'unknown'),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        return None

def format_tweet_text(tweet):
    """
    格式化推文文本，展开URLs并添加媒体描述
    :param tweet: Tweet对象
    :return: 格式化后的推文文本
    """
    try:
        text = tweet.text
        if not hasattr(tweet, 'entities') or 'urls' not in tweet.entities:
            return text

        # 按URL长度排序，避免替换冲突
        urls = sorted(tweet.entities['urls'], key=lambda x: len(x['url']), reverse=True)
        
        for url in urls:
            if 'url' in url and 'expanded_url' in url:
                # 如果有标题，只使用标题
                if 'title' in url and url['title']:
                    replacement = url['title']
                else:
                    # 如果没有标题，使用display_url
                    replacement = url.get('display_url', url['expanded_url'])
                text = text.replace(url['url'], replacement)
        
        return text
    except Exception as e:
        logger.error(f"格式化推文文本时出错: {str(e)}")
        return tweet.text

class CacheManager:
    def __init__(self, cache_file=CACHE_FILE, max_size=MAX_CACHE_SIZE, expire_hours=CACHE_EXPIRE_HOURS):
        self.cache_file = cache_file
        self.max_size = max_size
        self.expire_hours = expire_hours
        self.cache_data = {}
        self.current_size = 0
        self.load_cache()

    def load_cache(self):
        """加载缓存数据"""
        if os.path.exists(self.cache_file):
            try:
                # 检查文件大小
                if os.path.getsize(self.cache_file) == 0:
                    logger.warning(f"缓存文件 {self.cache_file} 为空")
                    return

                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    try:
                        self.cache_data = json.load(f)
                        self.current_size = len(json.dumps(self.cache_data).encode('utf-8'))
                    except json.JSONDecodeError as e:
                        logger.error(f"缓存文件 {self.cache_file} JSON格式错误: {str(e)}")
                        self._backup_corrupted_cache()
                        self.cache_data = {}
                        self.current_size = 0

            except Exception as e:
                logger.error(f"加载缓存文件失败: {str(e)}")
                self.cache_data = {}
                self.current_size = 0

    def _backup_corrupted_cache(self):
        """备份损坏的缓存文件"""
        try:
            backup_file = f"{self.cache_file}.bak"
            os.rename(self.cache_file, backup_file)
            logger.info(f"已将损坏的缓存文件备份为: {backup_file}")
        except Exception as e:
            logger.error(f"备份缓存文件失败: {str(e)}")

    def save_cache(self):
        """保存缓存数据"""
        temp_file = f"{self.cache_file}.tmp"
        try:
            # 检查并清理缓存大小
            self._cleanup_size()
            
            # 将缓存数据转换为可序列化格式
            serializable_cache = {}
            for key, value in self.cache_data.items():
                if 'tweets' in value:
                    serializable_cache[key] = {
                        'tweets': [self._serialize_tweet(tweet) for tweet in value['tweets']],
                        'timestamp': value['timestamp']
                    }
            
            # 原子写入
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, self.cache_file)
            
            logger.info(f"缓存已保存到: {self.cache_file}")
        except Exception as e:
            logger.error(f"保存缓存失败: {str(e)}")
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.error(f"删除临时文件失败: {str(e)}")

    def _cleanup_size(self):
        """清理超出大小限制的缓存数据"""
        if self.current_size <= self.max_size:
            return

        try:
            # 按时间戳排序
            sorted_items = sorted(
                self.cache_data.items(),
                key=lambda x: datetime.fromisoformat(x[1]['timestamp'])
            )
            
            # 删除最旧的数据直到大小符合要求
            while self.current_size > self.max_size and sorted_items:
                key, value = sorted_items.pop(0)
                value_size = len(json.dumps(value).encode('utf-8'))
                del self.cache_data[key]
                self.current_size -= value_size
            
            logger.info(f"缓存大小已清理至 {self.current_size / 1024 / 1024:.2f}MB")
        except Exception as e:
            logger.error(f"清理缓存大小时出错: {str(e)}")

    def add_to_cache(self, key, value):
        """添加数据到缓存"""
        try:
            json_str = json.dumps(value, default=str)
            value_size = len(json_str.encode('utf-8'))
            
            if self.current_size + value_size > self.max_size:
                self._cleanup_size()
            
            self.cache_data[key] = value
            self.current_size += value_size
            self.save_cache()
        except Exception as e:
            logger.error(f"添加缓存数据失败: {str(e)}")

    def get(self, key):
        """获取缓存数据"""
        return self.cache_data.get(key)

    def set(self, key, value):
        """设置缓存数据"""
        self.add_to_cache(key, value)

    def is_valid(self, key):
        """检查缓存是否有效"""
        if key not in self.cache_data:
            return False
            
        cache_time = self.cache_data[key].get('timestamp')
        if not cache_time:
            return False
            
        try:
            cache_datetime = datetime.fromisoformat(cache_time)
            return datetime.now() - cache_datetime < timedelta(hours=self.expire_hours)
        except ValueError:
            return False

    def _serialize_tweet(self, tweet):
        """专门的推文序列化函数"""
        if isinstance(tweet, dict):
            return tweet
        return {
            'id': str(tweet.id),
            'created_at': tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else None,
            # ... 其他字段
        }

# 创建全局缓存管理器实例
cache_manager = CacheManager()

class PerformanceMonitor:
    """性能监控类"""
    def __init__(self):
        self.start_time = None
        self.operation = None
        self.metrics = {
            'api_calls': 0,
            'cache_hits': 0,
            'processing_time': 0
        }

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.operation:
            duration = time.time() - self.start_time
            perf_logger.info(f"{self.operation} 耗时: {duration:.2f}秒")

    def set_operation(self, operation):
        self.operation = operation

def log_performance(operation):
    """性能日志装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with PerformanceMonitor() as monitor:
                monitor.set_operation(operation)
                return func(*args, **kwargs)
        return wrapper
    return decorator

@log_performance("获取用户推文")
def get_user_tweets(client, username, max_results=5, include_replies=False, include_retweets=False, start_time=None, end_time=None):
    """
    获取指定用户的推文
    :param client: Twitter API客户端
    :param username: 目标用户名
    :param max_results: 获取的推文数量
    :param include_replies: 是否包含回复
    :param include_retweets: 是否包含转发
    :param start_time: 开始时间
    :param end_time: 结束时间
    :return: 推文列表
    """
    try:
        print_info(f"\n正在获取用户 {username} 的推文...")
        
        # 验证参数
        max_results = validate_max_results(max_results)
        
        # 构建缓存键
        cache_key = f"{username}_{max_results}_{include_replies}_{include_retweets}"
        if start_time:
            cache_key += f"_{start_time.isoformat()}"
        if end_time:
            cache_key += f"_{end_time.isoformat()}"
        
        # 使用缓存管理器
        if cache_manager.is_valid(cache_key):
            logger.info("从缓存中获取数据")
            return cache_manager.get(cache_key)['tweets']

        tweets_data = []
        pagination_token = None
        remaining_results = max(max_results, MIN_RESULTS_PER_REQUEST)
        retry_count = 0
        max_retries = 3

        # 获取用户信息
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

        # 构建API参数
        tweet_params = {
            'id': user_id,
            'max_results': min(remaining_results, MAX_RESULTS_PER_REQUEST),
            'tweet_fields': [
                'created_at',
                'text',
                'public_metrics',
                'entities',
                'referenced_tweets',
                'attachments',
                'author_id',
                'context_annotations',
                'conversation_id',
                'in_reply_to_user_id',
                'lang'
            ],
            'expansions': [
                'referenced_tweets.id',
                'referenced_tweets.id.author_id',
                'entities.mentions.username',
                'attachments.media_keys',
                'attachments.poll_ids',
                'author_id',
                'in_reply_to_user_id'
            ],
            'media_fields': [
                'url',
                'preview_image_url',
                'type',
                'height',
                'width',
                'alt_text',
                'duration_ms'
            ],
            'user_fields': [
                'name',
                'username',
                'profile_image_url',
                'verified'
            ]
        }
        
        if not include_replies:
            tweet_params['exclude'] = ['replies']
        if start_time:
            tweet_params['start_time'] = start_time.isoformat()
        if end_time:
            tweet_params['end_time'] = end_time.isoformat()

        # 获取推文
        with ProgressBar(max_results, desc="获取推文") as pbar:
            while remaining_results > 0 and retry_count < max_retries:
                try:
                    tweet_params['max_results'] = min(remaining_results, MAX_RESULTS_PER_REQUEST)
                    if pagination_token:
                        tweet_params['pagination_token'] = pagination_token
                    
                    logger.info(f"正在获取 {tweet_params['max_results']} 条推文")
                    tweets = client.make_request(
                        lambda client: client.get_users_tweets(**tweet_params),
                        'get_users_tweets'
                    )

                    if not tweets or not hasattr(tweets, 'data') or not tweets.data:
                        logger.warning("未获取到推文数据")
                        break

                    current_tweets = []
                    if not include_retweets:
                        current_tweets = [
                            tweet for tweet in tweets.data
                            if (not hasattr(tweet, 'referenced_tweets') or 
                                not tweet.referenced_tweets or
                                not any(ref.type == 'retweeted' for ref in tweet.referenced_tweets))
                        ]
                    else:
                        current_tweets = tweets.data

                    tweets_data.extend(current_tweets)
                    pbar.update(len(current_tweets))
                    
                    # 更新剩余需要获取的推文数量
                    remaining_results = max_results - len(tweets_data)
                    
                    if remaining_results <= 0:
                        break

                    if hasattr(tweets, 'meta') and tweets.meta and tweets.meta.get('next_token') and remaining_results > 0:
                        pagination_token = tweets.meta['next_token']
                        time.sleep(2)  # 添加延迟以避免速率限制
                    else:
                        break

                except tweepy.TooManyRequests as e:
                    wait_time = (2 ** retry_count) * 5
                    logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                    
                except Exception as e:
                    logger.error(f"获取推文时发生错误: {str(e)}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        break
                    time.sleep(5)

        # 更新缓存
        if tweets_data:
            try:
                # 将tweets转换为可序列化的字典列表
                serializable_tweets = []
                for tweet in tweets_data[:max_results]:
                    # 确保includes数据可用
                    includes_data = tweets.includes if hasattr(tweets, 'includes') else None
                    # 转换为字典
                    tweet_dict = {
                        'id': str(tweet.id),
                        'created_at': tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else None,
                        'text': tweet.text if hasattr(tweet, 'text') else '',
                        'public_metrics': tweet.public_metrics if hasattr(tweet, 'public_metrics') else {},
                        'entities': tweet.entities if hasattr(tweet, 'entities') else {},
                        'referenced_tweets': tweet.referenced_tweets if hasattr(tweet, 'referenced_tweets') else [],
                        'attachments': tweet.attachments if hasattr(tweet, 'attachments') else {}
                    }
                    serializable_tweets.append(tweet_dict)

                # 存入缓存
                cache_data = {
                    'tweets': serializable_tweets,
                    'timestamp': datetime.now().isoformat()
                }
                cache_manager.set(cache_key, cache_data)
                print_success(f"\n成功获取 {len(serializable_tweets)} 条推文")

            except Exception as e:
                logger.error(f"处理缓存数据时出错: {str(e)}")
                # 即使缓存失败，仍然返回原始数据
                return tweets_data[:max_results]

        return tweets_data[:max_results]
        
    except Exception as e:
        print_error(f"\n获取推文过程中发生错误: {str(e)}")
        return []
    finally:
        logger.info(f"完成获取用户 {username} 的推文")

@log_performance("导出推文")
def export_tweets(tweets, format_type, filename=None):
    """
    导出推文数据到文件
    :param tweets: 要导出的推文列表（可以是Tweet对象或字典）
    :param format_type: 导出格式（'json' 或 'csv'）
    :param filename: 输出文件名（可选）
    :return: 导出文件的路径，失败时返回None
    """
    if not tweets:
        print_warning("没有可导出的推文数据")
        return None
        
    try:
        if format_type not in EXPORT_FORMATS:
            print_error(f"不支持的导出格式: {format_type}")
            return None
            
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tweets_{timestamp}.{format_type}"
            
        print_info(f"\n正在导出 {len(tweets)} 条推文到 {filename}...")
        
        with ProgressBar(len(tweets), desc="导出数据") as pbar:
            if format_type == 'json':
                data = []
                for tweet in tweets:
                    if isinstance(tweet, dict):
                        data.append(tweet)
                    else:
                        tweet_dict = tweet_to_dict(tweet)
                        if tweet_dict:
                            data.append(tweet_dict)
                    pbar.update()
                    
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
            elif format_type == 'csv':
                import csv
                with open(filename, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', '发布时间', '内容', '点赞数', '转发数', '回复数'])
                    
                    for tweet in tweets:
                        if isinstance(tweet, dict):
                            metrics = tweet.get('metrics', {})
                            writer.writerow([
                                tweet.get('id', ''),
                                tweet.get('created_at', ''),
                                tweet.get('text', ''),
                                metrics.get('like_count', 0),
                                metrics.get('retweet_count', 0),
                                metrics.get('reply_count', 0)
                            ])
                        else:
                            metrics = tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
                            writer.writerow([
                                tweet.id,
                                tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else '',
                                format_tweet_text(tweet),
                                metrics.get('like_count', 0),
                                metrics.get('retweet_count', 0),
                                metrics.get('reply_count', 0)
                            ])
                        pbar.update()
                        
        print_success(f"\n数据已成功导出到: {filename}")
        return filename
        
    except Exception as e:
        print_error(f"\n导出数据时出错: {str(e)}")
        logger.error(f"导出数据时出错: {str(e)}")
        return None

def validate_max_results(value):
    """
    验证获取推文数量参数
    :param value: 要验证的数值
    :return: 验证后的整数值
    :raises ValueError: 当输入值无效时
    """
    try:
        max_results = int(value)
        if max_results <= 0:
            raise ValueError("获取推文数量必须大于0")
        return max_results
    except ValueError as e:
        raise ValueError(f"无效的推文数量: {str(e)}")

def handle_get_tweets(twitter_client):
    """
    处理获取推文的功能
    包括用户输入处理、参数验证、推文获取和显示
    :param twitter_client: Twitter API客户端
    """
    try:
        target_username = input("请输入要爬取的Twitter用户名（不包含@符号）: ").strip()
        if not target_username:
            print_error("用户名不能为空")
            return

        max_results = input("请输入要获取的推文数量（默认5条）: ").strip()
        max_results = validate_max_results(max_results) if max_results else 5

        include_replies = input("是否包含回复（y/n，默认n）: ").lower().strip() == 'y'
        include_retweets = input("是否包含转发（y/n，默认n）: ").lower().strip() == 'y'

        start_time, end_time = get_time_range()

        tweets = get_user_tweets(
            twitter_client,
            target_username,
            max_results=max_results,
            include_replies=include_replies,
            include_retweets=include_retweets,
            start_time=start_time,
            end_time=end_time
        )

        if not tweets:
            return

        display_tweets(tweets)
        handle_export(tweets)

    except ValueError as e:
        print_error(f"输入错误: {str(e)}")
    except Exception as e:
        print_error(f"操作失败: {str(e)}")
        logger.error(f"获取推文操作失败: {str(e)}", exc_info=True)

def get_time_range():
    """
    获取用户输入的时间范围
    :return: (开始时间, 结束时间) 的元组，如果未指定则为None
    """
    start_time = end_time = None
    use_time_filter = input("是否按时间范围筛选（y/n，默认n）: ").lower().strip() == 'y'

    if use_time_filter:
        try:
            print("请输入起始时间（格式：YYYY-MM-DD，留空表示不限制）:")
            start_date = input().strip()
            if start_date:
                start_time = datetime.strptime(start_date, '%Y-%m-%d')

            print("请输入结束时间（格式：YYYY-MM-DD，留空表示不限制）:")
            end_date = input().strip()
            if end_date:
                end_time = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError as e:
            print_error(f"日期格式错误: {str(e)}")
            return None, None

    return start_time, end_time

def display_tweets(tweets, format_type='detailed'):
    """
    显示推文内容
    :param tweets: 推文列表（可以是Tweet对象或字典）
    :param format_type: 显示格式（'detailed' 或 'simple' 或 'compact'）
    """
    for tweet in tweets:
        try:
            print(f"\n{'='*80}")
            
            # 判断是Tweet对象还是字典
            if isinstance(tweet, dict):
                # 已经是字典格式
                created_at = tweet.get('created_at', 'N/A')
                text = tweet.get('text', 'N/A')
                media = tweet.get('media', [])
                referenced_tweets = tweet.get('referenced_tweets', [])
                metrics = tweet.get('metrics', {})
            else:
                # Tweet对象，需要转换
                created_at = tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else 'N/A'
                text = format_tweet_text(tweet)
                media = tweet.media if hasattr(tweet, 'media') else []
                referenced_tweets = tweet.referenced_tweets if hasattr(tweet, 'referenced_tweets') else []
                metrics = tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
            
            print(f"发布时间: {created_at}")
            print(f"\n{text}\n")
            
            # 显示媒体内容
            if media:
                print("\n媒体内容:")
                for m in media:
                    print(f"- 类型: {m.get('type', 'N/A')}")
                    print(f"  链接: {m.get('url', 'N/A')}")
                    if m.get('alt_text'):
                        print(f"  描述: {m['alt_text']}")
            
            # 显示引用推文
            if referenced_tweets:
                print("\n引用推文:")
                for ref in referenced_tweets:
                    print(f"- 类型: {ref.get('type', 'N/A')}")
                    print(f"  内容: {ref.get('text', 'N/A')}")
            
            # 显示互动数据
            print(f"\n👍 {metrics.get('like_count', 0)} | 🔄 {metrics.get('retweet_count', 0)} | 💬 {metrics.get('reply_count', 0)} | 📝 {metrics.get('quote_count', 0)}")
            print(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"显示推文时出错: {str(e)}")
            print_error("显示该条推文时出错，已跳过")

def handle_export(tweets):
    """
    处理导出功能
    提供交互式的导出格式选择和文件保存
    :param tweets: 要导出的推文列表
    """
    if input("\n是否要导出数据（y/n）: ").lower().strip() == 'y':
        print("\n可用的导出格式：")
        for i, fmt in enumerate(EXPORT_FORMATS, 1):
            print_info(f"{i}. {fmt}")

        try:
            format_choice = int(input("\n请选择导出格式（输入序号）: ").strip())
            if 1 <= format_choice <= len(EXPORT_FORMATS):
                format_type = EXPORT_FORMATS[format_choice - 1]
                export_tweets(tweets, format_type)
            else:
                print_error("无效的选择")
        except ValueError:
            print_error("无效的输入")

def handle_api_status(twitter_client):
    """
    处理API状态查询功能
    显示各个API端点的使用情况和剩余配额
    :param twitter_client: Twitter API客户端
    """
    try:
        remaining_get_user = twitter_client.rate_limiter.get_remaining_requests('get_user')
        remaining_get_tweets = twitter_client.rate_limiter.get_remaining_requests('get_users_tweets')

        print("\nAPI使用情况:")
        print_info("获取用户信息:")
        print(f"  - 总配额: {twitter_client.rate_limiter.endpoint_limits['get_user']['limit']}")
        print(f"  - 已使用: {twitter_client.rate_limiter.endpoint_limits['get_user']['limit'] - remaining_get_user}")
        print(f"  - 剩余配额: {remaining_get_user}")

        if twitter_client.rate_limiter.requests['get_user']:
            print(f"  - 重置时间: {twitter_client.rate_limiter._get_wait_time('get_user'):.1f} 秒后")

        print_info("\n获取推文:")
        print(f"  - 总配额: {twitter_client.rate_limiter.endpoint_limits['get_users_tweets']['limit']}")
        print(f"  - 已使用: {twitter_client.rate_limiter.endpoint_limits['get_users_tweets']['limit'] - remaining_get_tweets}")
        print(f"  - 剩余配额: {remaining_get_tweets}")

        if twitter_client.rate_limiter.requests['get_users_tweets']:
            print(f"  - 重置时间: {twitter_client.rate_limiter._get_wait_time('get_users_tweets'):.1f} 秒后")

    except Exception as e:
        print_error(f"获取API使用情况时发生错误: {str(e)}")
        logger.error(f"获取API状态失败: {str(e)}", exc_info=True)

def handle_clear_cache():
    """
    处理清除缓存功能
    删除缓存文件并显示操作结果
    """
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print_success("缓存已清除")
        else:
            print_warning("没有找到缓存文件")
    except Exception as e:
        print_error(f"清除缓存失败: {str(e)}")
        logger.error(f"清除缓存失败: {str(e)}", exc_info=True)

def main():
    """
    主函数
    提供交互式菜单，处理用户选择和程序流程控制
    包括：
    1. 初始化Twitter客户端
    2. 提供功能菜单
    3. 处理用户输入
    4. 错误处理和程序退出
    """
    try:
        twitter_client = RetryableTwitterClient()
        if not twitter_client.clients:
            print_error("API客户端初始化失败")
            return

        actions = {
            '1': lambda: handle_get_tweets(twitter_client),
            '2': lambda: handle_api_status(twitter_client),
            '3': handle_clear_cache,
            '4': lambda: print_warning("\n请注意：只能导出最近一次获取的推文数据\n如需导出其他数据，请先使用选项1获取推文")
        }

        while True:
            print("\n" + "="*20 + " Twitter爬虫工具 " + "="*20)
            print_info("""
1. 获取用户推文
2. 显示API使用情况
3. 清除缓存
4. 导出数据
q. 退出
            """)

            choice = input("\n请选择操作: ").strip()

            if choice == 'q':
                print_info("\n感谢使用,再见!")
                break
            elif choice in actions:
                actions[choice]()
            else:
                print_error("无效的选择，请重试")

    except KeyboardInterrupt:
        print_info("\n\n程序已终止")
    except Exception as e:
        print_error(f"\n程序发生错误: {str(e)}")
        logger.error(f"程序运行时错误: {str(e)}", exc_info=True)
    finally:
        colorama.deinit()

if __name__ == "__main__":
    main() 