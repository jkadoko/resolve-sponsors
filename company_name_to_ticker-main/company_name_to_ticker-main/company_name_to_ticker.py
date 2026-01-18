#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Company Name to Ticker Converter - FIXED to match test3.py logic exactly
修复版本，完全匹配test3.py的逻辑
"""

import json
import pandas as pd
import os
import re
import requests
import time
import urllib.parse
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional, Dict, List, Tuple


class EnhancedTest3TickerConverter:
    def __init__(self,
                 company_tickers_file="company_tickers.json",
                 company_tickers_exchange_file="company_tickers_exchange.json"):
        """
        Initialize the enhanced test3.py logic ticker converter
        """
        self.companies_data = []

        # Load local SEC data - 使用与test3.py完全相同的加载逻辑
        self.load_local_data(company_tickers_exchange_file, company_tickers_file)

        # Company suffixes from test3.py
        self.company_suffixes = [
            'INC', 'CORP', 'CORPORATION', 'LTD', 'LIMITED', 'LLC', 'LP', 'LLP',
            'CO', 'COMPANY', 'HOLDINGS', 'GROUP', 'ENTERPRISES', 'SYSTEMS',
            'TECHNOLOGIES', 'TECH', 'SOLUTIONS', 'SERVICES', 'INTERNATIONAL',
            'PLC', 'SA', 'NV', 'AG', 'GMBH', 'SPA', 'BV', 'NEW'  # Added NEW from test3.py
        ]

    def load_local_data(self, json_file1: str, json_file2: str):
        """
        加载本地JSON文件数据 - 完全使用test3.py的逻辑
        json_file1: company_tickers_exchange.json
        json_file2: company_tickers.json
        """
        # 加载第一个文件 (company_tickers_exchange.json)
        try:
            with open(json_file1, 'r', encoding='utf-8') as f:
                data1 = json.load(f)
                if 'data' in data1 and 'fields' in data1:
                    fields = data1['fields']
                    name_idx = fields.index('name')
                    ticker_idx = fields.index('ticker')
                    for row in data1['data']:
                        self.companies_data.append({
                            'name': row[name_idx],
                            'ticker': row[ticker_idx],
                            'source': 'file1'
                        })
        except FileNotFoundError:
            print(f"警告: 无法找到文件 {json_file1}")
        except Exception as e:
            print(f"加载文件 {json_file1} 时出错: {e}")

        # 加载第二个文件 (company_tickers.json)
        try:
            with open(json_file2, 'r', encoding='utf-8') as f:
                data2 = json.load(f)
                for key, company in data2.items():
                    if isinstance(company, dict) and 'title' in company and 'ticker' in company:
                        existing_tickers = [comp['ticker'] for comp in self.companies_data]
                        if company['ticker'] not in existing_tickers:
                            self.companies_data.append({
                                'name': company['title'],
                                'ticker': company['ticker'],
                                'source': 'file2'
                            })
        except FileNotFoundError:
            print(f"警告: 无法找到文件 {json_file2}")
        except Exception as e:
            print(f"加载文件 {json_file2} 时出错: {e}")

        print(f"成功加载 {len(self.companies_data)} 家公司的数据")

    def extract_core_keywords(self, company_name: str) -> List[str]:
        """提取公司名称中的核心关键词（简化版，用于在线搜索）"""
        name = company_name.upper().strip()

        # 移除公司后缀
        for suffix in self.company_suffixes:
            name = re.sub(rf'\b{suffix}\b', '', name)

        # 清理标点符号
        name = re.sub(r'[.,&\-/()]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()

        # 分割并过滤短词和常见词
        stop_words = {'THE', 'OF', 'AND', 'OR', 'FOR', 'WITH', 'A', 'AN', 'AT', 'BY', 'IN', 'ON'}
        keywords = [word for word in name.split()
                    if len(word) >= 2 and word not in stop_words]  # 降低最小长度到2

        return keywords

    def calculate_company_similarity(self, name1: str, name2: str) -> float:
        """计算公司名称的相似度（采用test3.py的逻辑）"""
        norm1 = self.normalize_company_name(name1)
        norm2 = self.normalize_company_name(name2)

        # 完全匹配
        if norm1 == norm2:
            return 1.0

        # 避免错误的部分匹配（如 ALLERGAN 和 ARGAN）
        # 检查是否一个是否另一个的真正子串
        if norm1 and norm2:
            # 如果两个名称长度差异很大，降低相似度
            len_diff = abs(len(norm1) - len(norm2))
            if len_diff > max(len(norm1), len(norm2)) * 0.3:  # 长度差异超过30%
                base_ratio = SequenceMatcher(None, norm1, norm2).ratio()
                # 对长度差异很大的情况进行惩罚
                return base_ratio * (1 - len_diff / max(len(norm1), len(norm2)))

            # 检查是否是真正的包含关系
            if norm1 in norm2 or norm2 in norm1:
                shorter = norm1 if len(norm1) < len(norm2) else norm2
                longer = norm2 if len(norm1) < len(norm2) else norm1

                # 如果较短的名称占较长名称的比例很高，才认为是包含关系
                if len(shorter) >= len(longer) * 0.7:
                    return 0.9
                else:
                    # 否则降低相似度
                    return SequenceMatcher(None, norm1, norm2).ratio() * 0.8

        # 序列匹配
        return SequenceMatcher(None, norm1, norm2).ratio()

    def normalize_company_name(self, name: str) -> str:
        """标准化公司名称（采用test3.py的逻辑）"""
        name = name.upper().strip()
        name = re.sub(r'[.,&\-/]', ' ', name)
        name = re.sub(r'\s+', ' ', name)

        words = name.split()
        filtered_words = []
        for word in words:
            if word not in self.company_suffixes:
                filtered_words.append(word)

        return ' '.join(filtered_words).strip()

    def search_local(self, company_name: str, threshold: float = 0.75) -> List[Tuple[Dict, float]]:
        """
        在本地数据中搜索 - 完全使用test3.py的逻辑
        """
        results = []

        for company in self.companies_data:
            similarity = self.calculate_company_similarity(company_name, company['name'])
            if similarity >= threshold:
                results.append((company, similarity))

        results.sort(key=lambda x: x[1], reverse=True)

        # test3.py的额外验证：检查最佳匹配是否真的合理
        if results:
            best_match = results[0]
            best_similarity = best_match[1]
            best_company = best_match[0]

            # 进行关键词检查验证
            user_keywords = set(self.extract_core_keywords(company_name))
            match_keywords = set(self.extract_core_keywords(best_company['name']))

            # 计算关键词重叠
            intersection = user_keywords.intersection(match_keywords)

            # 如果没有任何关键词重叠，但相似度很高，这可能是错误匹配
            if len(intersection) == 0 and best_similarity > 0.8:
                print(f"警告：高相似度但无关键词重叠，可能是错误匹配")
                print(f"用户关键词: {user_keywords}")
                print(f"匹配关键词: {match_keywords}")
                print(f"跳过可疑匹配: {best_company['name']} (相似度: {best_similarity:.2f})")
                return []

            # 如果只有一个字符的重叠，也要谨慎
            if len(intersection) == 0:
                # 检查字符级别的相似度是否合理
                norm1 = self.normalize_company_name(company_name)
                norm2 = self.normalize_company_name(best_company['name'])

                # 计算长度差异
                len_diff = abs(len(norm1) - len(norm2))
                max_len = max(len(norm1), len(norm2))
                len_similarity = 1 - (len_diff / max_len) if max_len > 0 else 0

                # 如果长度差异太大，也认为是可疑匹配
                if len_similarity < 0.5 and best_similarity > 0.7:
                    print(f"警告：长度差异过大的可疑匹配")
                    print(f"'{norm1}' vs '{norm2}'")
                    print(f"长度相似度: {len_similarity:.2f}, 总相似度: {best_similarity:.2f}")
                    return []

        # 额外检查：如果最佳匹配的相似度不够高，可能是错误匹配
        if results and results[0][1] < 0.85:
            print(f"警告：最佳本地匹配相似度较低 ({results[0][1]:.2f})，可能不准确")
            if results[0][1] < 0.80:
                print("相似度过低，跳过本地匹配，直接进行在线搜索")
                return []

        return results

    def validate_ticker_with_company_verification(self, ticker: str, company_name: str) -> bool:
        """通过在线验证股票代码与公司的匹配性 - 加强版"""
        try:
            # 使用Yahoo Finance验证
            yahoo_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(yahoo_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'chart' in data and data['chart']['result']:
                    result = data['chart']['result'][0]
                    meta = result.get('meta', {})
                    symbol_name = meta.get('longName', '') or meta.get('shortName', '')

                    if symbol_name:
                        similarity = self.calculate_company_similarity(company_name, symbol_name)
                        print(f"Yahoo验证: {ticker} -> {symbol_name} (相似度: {similarity:.2f})")

                        # 大幅提高验证阈值，避免错误匹配
                        if similarity > 0.75:  # 从0.6提高到0.75
                            return True
                        else:
                            print(f"相似度过低({similarity:.2f})，Yahoo验证失败")
                            return False

                        # 对于退市股票，Yahoo可能返回不完整信息，进行额外检查
                        if not symbol_name or len(symbol_name) < 5:
                            print(f"Yahoo返回信息不完整，尝试其他验证方法")
                            return self.strict_fallback_verification(ticker, company_name)
                    else:
                        # 没有公司名称信息，可能是退市股票
                        print(f"Yahoo无公司名称信息，可能是退市股票: {ticker}")
                        return self.strict_fallback_verification(ticker, company_name)

            # Yahoo验证失败，尝试备用验证
            return self.strict_fallback_verification(ticker, company_name)

        except Exception as e:
            print(f"股票代码验证错误: {e}")
            # 验证失败时，如果ticker格式正确且在合理上下文中，也可能是有效的
            return self.strict_fallback_verification(ticker, company_name)

    def strict_fallback_verification(self, ticker: str, company_name: str) -> bool:
        """严格的备用验证方法"""
        try:
            # 方法1: 检查ticker是否为常见的已知股票代码格式
            if len(ticker) >= 2 and ticker.isalpha() and ticker.isupper():
                # 严格检查是否在常见的错误列表中
                common_false_positives = {
                    'THE', 'AND', 'FOR', 'WITH', 'FROM', 'HTML', 'HTTP', 'HTTPS',
                    'NEWS', 'INFO', 'HELP', 'MORE', 'ABOUT', 'CONTACT', 'HOME',
                    'MAIN', 'MENU', 'SEARCH', 'LOGIN', 'PAGE', 'SITE', 'LINK',
                    'NYSE', 'NASDAQ', 'NASDA', 'NASD', 'MKT', 'COM', 'ORG', 'NET'
                }
                if ticker in common_false_positives:
                    print(f"ticker在错误列表中，备用验证失败: {ticker}")
                    return False

                # 进行基本的字符匹配检查
                company_chars = set(self.normalize_company_name(company_name).replace(' ', ''))
                ticker_chars = set(ticker)

                # 检查ticker的字符是否大部分都能在公司名称中找到
                matching_chars = ticker_chars.intersection(company_chars)
                if len(matching_chars) >= len(ticker_chars) * 0.6:  # 至少60%的字符匹配
                    print(f"字符匹配验证通过: {ticker} (匹配字符: {matching_chars})")
                    return True
                else:
                    print(f"字符匹配验证失败: {ticker} (匹配字符: {matching_chars}, 需要: {ticker_chars})")
                    return False

            # 方法2: 尝试Alpha Vantage验证（如果可用）
            time.sleep(1)
            return self.verify_with_alpha_vantage(ticker, company_name)

        except Exception as e:
            print(f"严格备用验证错误: {e}")
            return False

    def verify_with_alpha_vantage(self, ticker: str, company_name: str) -> bool:
        """使用Alpha Vantage验证"""
        try:
            # 使用demo key进行基本验证
            search_url = "https://www.alphavantage.co/query"
            params = {
                'function': 'SYMBOL_SEARCH',
                'keywords': ticker,
                'apikey': 'demo'
            }

            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'bestMatches' in data and data['bestMatches']:
                    for match in data['bestMatches']:
                        symbol = match.get('1. symbol', '')
                        if symbol.upper() == ticker.upper():
                            print(f"Alpha Vantage验证成功: {ticker}")
                            return True
        except:
            pass

        # 最后的宽松判断 - 但要更加谨慎
        if len(ticker) >= 2 and len(ticker) <= 5 and ticker.isalpha():
            # 额外检查：确保ticker不是明显的HTML/网页内容
            if not self.is_obviously_web_content(ticker):
                print(f"基于格式的谨慎验证: {ticker}")
                return True

        return False

    def is_obviously_web_content(self, ticker: str) -> bool:
        """检查是否明显是网页内容"""
        web_content_patterns = [
            r'^(DIV|SPAN|HTML|HEAD|BODY|TITLE|META)$',
            r'^(HTTP|HTTPS|WWW|FTP)$',
            r'^(NEWS|INFO|HELP|HOME|MAIN|MENU)$',
            r'^(LOGIN|SIGNUP|REGISTER|SUBMIT)$',
            r'^(ABOUT|CONTACT|PRIVACY|TERMS)$'
        ]

        for pattern in web_content_patterns:
            if re.match(pattern, ticker.upper()):
                return True
        return False

    def search_delisted_stocks_online(self, company_name: str) -> Optional[Dict]:
        """专门搜索退市股票信息"""
        print(f"正在网络搜索退市股票: {company_name}")

        try:
            # 方法1: 使用Yahoo Finance历史搜索
            result = self.search_yahoo_historical(company_name)
            if result:
                return result

            # 方法2: 搜索SEC EDGAR数据
            result = self.search_sec_edgar_enhanced(company_name)
            if result:
                return result

            # 方法3: 使用投资网站搜索
            result = self.search_investment_sites(company_name)
            if result:
                return result

            # 方法4: 通用网络搜索（改进版）
            result = self.search_web_general_enhanced(company_name)
            if result:
                return result

        except Exception as e:
            print(f"退市股票搜索错误: {e}")

        return None

    def search_yahoo_historical(self, company_name: str) -> Optional[Dict]:
        """通过Yahoo Finance搜索历史股票"""
        try:
            # Yahoo Finance有时会保留历史股票信息
            search_url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                'q': company_name,
                'lang': 'en-US',
                'region': 'US',
                'quotesCount': 10,
                'newsCount': 0
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(search_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'quotes' in data and data['quotes']:
                    for quote in data['quotes']:
                        symbol = quote.get('symbol', '')
                        quote_name = quote.get('longname', '') or quote.get('shortname', '')

                        if symbol and len(symbol) <= 5 and quote_name:
                            # 验证相似度
                            similarity = self.calculate_company_similarity(company_name, quote_name)
                            if similarity > 0.75:  # 提高阈值
                                print(f"Yahoo Finance历史搜索找到: {symbol} (相似度: {similarity:.2f})")
                                return {
                                    'ticker': symbol,
                                    'company_name': company_name,
                                    'source': 'yahoo_historical',
                                    'quote_type': quote.get('typeDisp', 'Unknown'),
                                    'matched_name': quote_name,
                                    'similarity': similarity
                                }
        except Exception as e:
            print(f"Yahoo历史搜索错误: {e}")
        return None

    def search_sec_edgar_enhanced(self, company_name: str) -> Optional[Dict]:
        """增强的SEC EDGAR搜索"""
        try:
            print(f"搜索SEC EDGAR: {company_name}")

            # SEC提供公司搜索API
            search_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'company': company_name,
                'match': 'contains',
                'action': 'getcompany'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; StockFinder/1.0; research-purpose)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }

            response = requests.get(search_url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                content = response.text

                # 提取公司关键词
                company_keywords = self.extract_core_keywords(company_name)

                # 查找Trading Symbol信息
                symbol_pattern = r'Trading Symbol[:\s]*([A-Z]{1,5})'
                match = re.search(symbol_pattern, content, re.IGNORECASE)
                if match:
                    ticker = match.group(1)
                    # 验证上下文
                    if self.validate_ticker_context(ticker, company_name, content):
                        print(f"SEC EDGAR找到验证的股票代码: {ticker}")
                        return {
                            'ticker': ticker,
                            'company_name': company_name,
                            'source': 'sec_edgar_enhanced'
                        }

                # 更严格的替代模式搜索
                ticker_patterns = [
                    r'symbol[:\s]+([A-Z]{2,5})',
                    r'ticker[:\s]+([A-Z]{2,5})',
                    r'NYSE[:\s]*([A-Z]{2,5})',
                    r'NASDAQ[:\s]*([A-Z]{2,5})'
                ]

                candidates = []
                for pattern in ticker_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if len(match) >= 2 and len(match) <= 5:
                            # 检查ticker周围是否有公司关键词
                            ticker_pos = content.upper().find(match)
                            if ticker_pos > 0:
                                context_start = max(0, ticker_pos - 200)
                                context_end = min(len(content), ticker_pos + 200)
                                context = content[context_start:context_end].upper()

                                keyword_found = any(keyword in context for keyword in company_keywords)
                                if keyword_found:
                                    candidates.append(match)

                # 验证候选股票代码
                for candidate in candidates:
                    if self.validate_ticker_with_company_verification(candidate, company_name):
                        print(f"SEC EDGAR验证成功: {candidate}")
                        return {
                            'ticker': candidate,
                            'company_name': company_name,
                            'source': 'sec_edgar_pattern'
                        }

        except Exception as e:
            print(f"SEC EDGAR搜索错误: {e}")
        return None

    def search_investment_sites(self, company_name: str) -> Optional[Dict]:
        """搜索投资网站"""
        sites = [
            {
                'name': 'MarketWatch',
                'url': 'https://www.marketwatch.com/tools/quotes/lookup.asp',
                'params': {'Lookup': company_name, 'Country': 'us'},
                'pattern': r'symbol=([A-Z]{1,5})'
            }
        ]

        for site in sites:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                response = requests.get(site['url'], params=site['params'],
                                        headers=headers, timeout=10)

                if response.status_code == 200:
                    content = response.text
                    matches = re.findall(site['pattern'], content, re.IGNORECASE)

                    for match in matches:
                        if len(match) <= 5:
                            # 验证股票代码
                            if self.validate_ticker_with_company_verification(match, company_name):
                                print(f"{site['name']}找到验证的股票代码: {match}")
                                return {
                                    'ticker': match,
                                    'company_name': company_name,
                                    'source': site['name'].lower()
                                }

                time.sleep(1)  # 避免请求过快

            except Exception as e:
                print(f"{site['name']}搜索错误: {e}")
                continue

        return None

    def search_web_general_enhanced(self, company_name: str) -> Optional[Dict]:
        """增强的通用网络搜索"""
        try:
            # 构造更精确的搜索查询
            search_queries = [
                f'"{company_name}" stock ticker symbol NYSE NASDAQ',
                f'"{company_name}" stock symbol trading',
                f'{company_name} ticker symbol exchange',
                f'"{company_name}" delisted stock ticker',
                f'{company_name} stock code symbol'
            ]

            for query in search_queries:
                print(f"网络搜索: {query}")

                # 使用DuckDuckGo搜索
                search_url = "https://html.duckduckgo.com/html/"
                params = {'q': query}

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                try:
                    response = requests.get(search_url, params=params, headers=headers, timeout=15)
                    if response.status_code == 200:
                        content = response.text

                        # 使用改进的候选提取方法
                        candidates = self.extract_ticker_candidates_enhanced(content, company_name)

                        # 验证每个候选 - 使用更严格的验证
                        for candidate in candidates:
                            print(f"正在验证候选股票代码: {candidate}")

                            # 首先进行基本有效性检查
                            if not self.is_valid_ticker(candidate):
                                continue

                            # 进行上下文验证
                            if self.validate_ticker_context(candidate, company_name, content):
                                print(f"上下文验证通过: {candidate}")

                                # 尝试在线验证，要求更严格
                                verification_result = self.validate_ticker_with_company_verification(candidate,
                                                                                                     company_name)
                                if verification_result:
                                    print(f"在线验证通过: {candidate}")
                                    return {
                                        'ticker': candidate,
                                        'company_name': company_name,
                                        'source': 'web_search_enhanced',
                                        'query': query,
                                        'verification': 'full'
                                    }
                                else:
                                    print(f"在线验证失败: {candidate}")
                                    # 不再接受仅通过上下文验证的结果

                    time.sleep(2)  # 避免被封IP

                except Exception as e:
                    print(f"搜索查询错误: {e}")
                    continue

        except Exception as e:
            print(f"增强网络搜索错误: {e}")

        return None

    def extract_ticker_candidates_enhanced(self, content: str, company_name: str) -> List[str]:
        """从内容中提取股票代码候选（改进版）"""
        company_keywords = self.extract_core_keywords(company_name)
        candidates = set()

        # 最精确的匹配模式 - 只匹配明确的股票代码格式
        precise_patterns = [
            # 明确的股票代码标识，带单词边界
            r'(?:ticker|stock\s+symbol|trading\s+symbol)[\s:]+([A-Z]{2,5})(?:\s|$|[^\w])',
            # 括号格式：完整的格式 (代码)
            r'\s\(([A-Z]{2,5})\)(?:\s|$|[^\w])',
            # NYSE/NASDAQ: 代码格式，确保不匹配交易所名称本身
            r'(?:NYSE|NASDAQ)[\s:]+([A-Z]{2,5})(?:\s|$|[^\w])(?!.*(?:exchange|market|website))',
        ]

        # 处理精确模式
        for pattern in precise_patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if self.is_valid_ticker_strict(match, company_name, content):
                        candidates.add(match.upper())
                        print(f"精确匹配找到: {match}")
            except Exception as e:
                print(f"精确模式匹配错误: {e}")
                continue

        # 如果精确匹配没找到，尝试上下文匹配
        if not candidates:
            candidates = self.extract_contextual_candidates(content, company_name)

        # 过滤和排序
        filtered_candidates = []
        for candidate in candidates:
            if not self.is_obviously_invalid(candidate):
                # 额外验证：检查是否真的与公司相关
                if self.validate_candidate_relevance(candidate, company_name, content):
                    filtered_candidates.append(candidate)

        # 按相关度排序：AGN类型的会排在前面
        sorted_candidates = sorted(filtered_candidates,
                                   key=lambda x: self.get_candidate_priority(x, company_name))

        print(f"过滤后的候选股票代码: {sorted_candidates}")
        return sorted_candidates

    def extract_contextual_candidates(self, content: str, company_name: str) -> set:
        """基于上下文提取候选股票代码"""
        candidates = set()
        company_keywords = self.extract_core_keywords(company_name)

        # 在公司关键词附近查找股票代码
        for keyword in company_keywords:
            # 查找关键词在内容中的位置
            keyword_positions = [m.start() for m in re.finditer(re.escape(keyword), content, re.IGNORECASE)]

            for pos in keyword_positions:
                # 在关键词前后100个字符内查找股票代码
                start = max(0, pos - 100)
                end = min(len(content), pos + 100)
                context = content[start:end]

                # 在这个上下文中查找股票代码
                context_patterns = [
                    r'\b([A-Z]{2,5})\b(?=\s*[:\-]|\s+(?:stock|shares|ticker|symbol))',
                    r'(?:ticker|symbol)[\s:]+([A-Z]{2,5})\b',
                    r'\(([A-Z]{2,5})\)',
                ]

                for pattern in context_patterns:
                    matches = re.findall(pattern, context)
                    for match in matches:
                        if self.is_valid_ticker_strict(match, company_name, context):
                            candidates.add(match.upper())
                            print(f"上下文匹配找到: {match}")

        return candidates

    def is_valid_ticker_strict(self, ticker: str, company_name: str, content: str) -> bool:
        """严格验证股票代码候选"""
        if not ticker or not isinstance(ticker, str):
            return False

        ticker = ticker.upper()

        # 基本格式检查
        if not (2 <= len(ticker) <= 5) or not ticker.isalpha():
            return False

        # 检查是否明显无效
        if self.is_obviously_invalid(ticker):
            return False

        # 检查是否为语言代码或国家代码
        if self.is_language_or_country_code(ticker):
            return False

        # 检查是否在股票相关上下文中
        if not self.is_in_strong_stock_context(ticker, content):
            return False

        return True

    def is_language_or_country_code(self, ticker: str) -> bool:
        """检查是否为语言代码或国家代码"""
        # 常见的语言代码
        language_codes = {
            'EN', 'FR', 'DE', 'ES', 'IT', 'PT', 'NL', 'RU', 'ZH', 'JA', 'KO',
            'AR', 'HI', 'TR', 'PL', 'CS', 'HU', 'RO', 'BG', 'HR', 'SK', 'SL',
            'ET', 'LV', 'LT', 'MT', 'DA', 'SV', 'FI', 'NO', 'IS', 'GA', 'CY'
        }

        # 常见的国家代码
        country_codes = {
            'US', 'UK', 'CA', 'AU', 'NZ', 'IE', 'ZA', 'IN', 'CN', 'JP', 'KR',
            'BR', 'MX', 'AR', 'CL', 'PE', 'CO', 'VE', 'UY', 'PY', 'BO', 'EC',
            'FR', 'DE', 'ES', 'IT', 'PT', 'NL', 'BE', 'LU', 'CH', 'AT', 'SE',
            'DK', 'NO', 'FI', 'IS', 'IE', 'MT', 'CY', 'GR', 'BG', 'RO', 'HU',
            'CZ', 'SK', 'PL', 'SI', 'HR', 'EE', 'LV', 'LT'
        }

        return ticker in language_codes or ticker in country_codes

    def is_in_strong_stock_context(self, ticker: str, content: str) -> bool:
        """检查是否在强股票上下文中（更严格的检查）"""
        # 强股票上下文指示词
        strong_stock_indicators = [
            'ticker symbol', 'stock symbol', 'trading symbol', 'stock ticker',
            'shares of', 'stock code', 'equity symbol', 'listed as',
            'trades as', 'symbol:', 'ticker:'
        ]

        # 查找ticker在内容中的位置
        ticker_positions = [m.start() for m in re.finditer(re.escape(ticker), content, re.IGNORECASE)]

        for pos in ticker_positions:
            # 检查前后50个字符
            start = max(0, pos - 50)
            end = min(len(content), pos + 50)
            context = content[start:end].lower()

            # 必须在强股票上下文中
            if any(indicator in context for indicator in strong_stock_indicators):
                return True

            # 检查是否在括号格式中：公司名 (TICKER)
            if '(' in context and ')' in context:
                bracket_start = context.rfind('(', 0, pos - start)
                bracket_end = context.find(')', pos - start)
                if bracket_start >= 0 and bracket_end >= 0:
                    return True

        return False

    def validate_candidate_relevance(self, ticker: str, company_name: str, content: str) -> bool:
        """验证候选股票代码与公司的相关性"""
        company_keywords = self.extract_core_keywords(company_name)

        # 检查ticker周围是否有公司关键词
        ticker_positions = [m.start() for m in re.finditer(re.escape(ticker), content, re.IGNORECASE)]

        for pos in ticker_positions:
            # 在ticker前后150个字符内查找公司关键词
            start = max(0, pos - 150)
            end = min(len(content), pos + 150)
            context = content[start:end].lower()

            # 计算在这个上下文中出现的公司关键词数量
            keyword_matches = sum(1 for keyword in company_keywords
                                  if keyword.lower() in context)

            # 如果有足够的关键词匹配，认为相关
            if keyword_matches >= max(1, len(company_keywords) // 2):
                return True

        return False

    def get_candidate_priority(self, ticker: str, company_name: str) -> int:
        """获取候选股票代码的优先级（越小优先级越高）"""
        # AGN类型的代码优先级最高
        if len(ticker) == 3:
            return 0
        # 4位代码次之
        elif len(ticker) == 4:
            return 1
        # 2位代码最低（通常是国家代码等）
        elif len(ticker) == 2:
            return 2
        # 5位代码
        else:
            return 3

    def validate_ticker_context(self, ticker: str, company_name: str, content: str) -> bool:
        """验证股票代码与公司名称的关联性 - 加强版"""
        if not self.is_valid_ticker(ticker):
            return False

        # 提取公司核心关键词
        company_keywords = self.extract_core_keywords(company_name)

        # 检查内容中是否包含足够的公司关键词
        content_lower = content.lower()

        # 对于短关键词或常见词，要求更严格的匹配
        keyword_matches = 0
        for keyword in company_keywords:
            keyword_lower = keyword.lower()

            # 检查关键词是否在内容中
            if keyword_lower in content_lower:
                # 进一步检查是否在ticker附近（±200字符内）
                ticker_positions = [m.start() for m in re.finditer(re.escape(ticker), content, re.IGNORECASE)]

                for pos in ticker_positions:
                    start = max(0, pos - 200)
                    end = min(len(content), pos + 200)
                    context = content[start:end].lower()

                    if keyword_lower in context:
                        keyword_matches += 1
                        break

        # 提高要求：至少要有一个关键词匹配，或者对于单关键词公司要求100%匹配
        if len(company_keywords) == 1:
            required_matches = 1
        else:
            required_matches = max(1, len(company_keywords) // 2)  # 至少1/2的关键词匹配

        print(f"关键词匹配情况: {keyword_matches}/{len(company_keywords)} (需要: {required_matches})")

        if keyword_matches >= required_matches:
            # 额外验证：确保不是巧合匹配
            return self.validate_contextual_relationship(ticker, company_name, content)

        # 备用检查：如果ticker和公司名在同一段落中出现
        paragraphs = re.split(r'\n\s*\n', content)
        for paragraph in paragraphs:
            if ticker.upper() in paragraph.upper():
                # 检查这个段落是否包含公司关键词
                paragraph_matches = sum(1 for keyword in company_keywords
                                        if keyword.lower() in paragraph.lower())
                if paragraph_matches > 0:
                    print(f"段落级匹配成功: {paragraph_matches} 个关键词")
                    return self.validate_contextual_relationship(ticker, company_name, paragraph)

        return False

    def validate_contextual_relationship(self, ticker: str, company_name: str, content: str) -> bool:
        """验证上下文关系的合理性"""
        # 检查是否存在明显的错误指向
        misleading_patterns = [
            r'(?:not|no|incorrect|wrong|error|mistake)\s+(?:ticker|symbol)',
            r'(?:different|other|another)\s+(?:company|corporation)',
            r'(?:formerly|previously|old)\s+(?:known|called)'
        ]

        content_lower = content.lower()
        for pattern in misleading_patterns:
            if re.search(pattern, content_lower):
                print(f"发现误导性模式，上下文验证失败: {pattern}")
                return False

        # 如果没有发现问题，则通过验证
        return True

    def is_valid_ticker(self, ticker: str) -> bool:
        """验证股票代码是否有效"""
        if not ticker or not isinstance(ticker, str):
            return False

        # 基本格式检查
        if not (1 <= len(ticker) <= 5):
            return False

        if not ticker.isupper() or not ticker.isalpha():
            return False

        # 使用新的检查方法
        return not self.is_obviously_invalid(ticker)

    def is_obviously_invalid(self, ticker: str) -> bool:
        """检查是否明显不是股票代码"""
        ticker_upper = ticker.upper()

        # 扩展的排除列表
        obvious_invalid = {
            # 交易所名称
            'NYSE', 'NASDAQ', 'NASDA', 'NASD', 'MKT',
            # 网页相关
            'HTML', 'HTTP', 'HTTPS', 'WWW', 'COM', 'ORG', 'NET', 'GOV',
            # 常见词汇
            'THE', 'AND', 'FOR', 'WITH', 'FROM', 'THIS', 'THAT',
            'MORE', 'ABOUT', 'CONTACT', 'NEWS', 'INFO', 'HELP',
            'PAGE', 'SITE', 'LINK', 'HREF', 'TEXT', 'FONT',
            # 搜索引擎相关
            'DDG', 'DUCK', 'GOOGLE', 'BING', 'YAHOO',
            # 公司后缀
            'INC', 'CORP', 'LTD', 'LLC', 'PLC',
            # 地理位置
            'USA', 'US', 'UK', 'CA', 'NY', 'IE', 'EU',
            # 其他常见误匹配
            'NEWS', 'HOME', 'MAIN', 'MENU', 'SEARCH', 'LOGIN',
            'MSN', 'CNN', 'BBC', 'ABC', 'CBS', 'NBC',
            # 网页内容相关（新增）
            'LINK', 'HREF', 'SRC', 'ALT', 'DIV', 'SPAN'
        }

        if ticker_upper in obvious_invalid:
            return True

        # 检查是否看起来像网站域名的一部分
        if ticker_upper.endswith('COM') or ticker_upper.endswith('NET'):
            return True

        # 检查是否看起来像HTML标签
        html_patterns = [
            r'^H[1-6]$',  # HTML标题
            r'^(BR|HR|TD|TR|TH|LI|UL|OL)$',  # HTML标签
            r'^(DIV|SPAN|FONT|BOLD)$',  # HTML容器
            r'^(SRC|ALT|REF|REL)$'  # HTML属性
        ]

        for pattern in html_patterns:
            if re.match(pattern, ticker_upper):
                return True

        return False

    def find_ticker(self, company_name: str, use_online: bool = True) -> Optional[Dict]:
        """
        查找公司的股票代码 - 完全使用test3.py的逻辑
        """
        if not company_name or pd.isna(company_name):
            return None

        print(f"\n正在搜索: {company_name}")

        # 1. 首先在本地数据中搜索 - 完全使用test3.py的逻辑
        local_results = self.search_local(company_name)
        if local_results:
            best_match = local_results[0]
            company_info = best_match[0]
            similarity = best_match[1]

            print(f"本地匹配找到: {company_info['name']} -> {company_info['ticker']}")
            return {
                'ticker': company_info['ticker'],
                'company_name': company_info['name'],
                'similarity': similarity,
                'source': 'local',
                'status': 'active'
            }

        # 2. 在线搜索
        if use_online:
            print("开始在线搜索...")
            delisted_result = self.search_delisted_stocks_online(company_name)
            if delisted_result:
                ticker = delisted_result['ticker']
                print(f"在线搜索找到: {company_name} -> {ticker}")

                return {
                    'ticker': ticker,
                    'company_name': company_name,
                    'source': delisted_result['source'],
                    'status': delisted_result.get('status', 'unknown'),
                    'search_method': delisted_result.get('query', 'multiple_methods'),
                    'similarity': delisted_result.get('similarity')
                }

            print("标准在线搜索未找到结果")

        print("未找到匹配的股票代码")
        return None

    def convert_csv_files(self, csv_pattern="*_all_quarters_merged.csv"):
        """
        转换所有匹配模式的CSV文件 - 使用完全匹配test3.py的逻辑
        """
        print("=" * 60)
        print("开始CSV文件转换 - 使用完全匹配test3.py的逻辑...")

        # 查找所有匹配的CSV文件
        current_dir = Path('.')
        csv_files = list(current_dir.glob(csv_pattern))

        if not csv_files:
            print(f"未找到匹配模式 '{csv_pattern}' 的CSV文件")
            return

        print(f"找到 {len(csv_files)} 个CSV文件需要处理")

        # 统计信息
        total_processed = 0
        total_matched = 0
        all_unmatched = set()

        for csv_file in csv_files:
            print(f"\n处理文件: {csv_file}")

            try:
                # 读取CSV文件
                df = pd.read_csv(csv_file)

                # 查找nameOfIssuer列
                name_column = None
                for col in df.columns:
                    if 'nameOfIssuer' in col or 'nameOfIssue' in col:
                        name_column = col
                        break

                if name_column is None:
                    print(f"  警告: 文件中未找到 'nameOfIssuer' 或 'nameOfIssue' 列")
                    print(f"  可用列: {list(df.columns)}")
                    continue

                # 创建新的DataFrame，包含必需的列: nameOfIssuer, Symbol, Source
                result_df = pd.DataFrame()

                tickers = []
                sources = []
                matched_count = 0

                print(f"  处理 {len(df)} 家公司...")

                for i, company_name in enumerate(df[name_column]):
                    if i % 10 == 0 and i > 0:
                        print(f"    进度: {i}/{len(df)} ({i / len(df) * 100:.1f}%)")

                    result = self.find_ticker(company_name, use_online=True)

                    if result:
                        tickers.append(result['ticker'])
                        sources.append(result['source'])
                        matched_count += 1
                    else:
                        tickers.append(None)
                        sources.append('not_found')
                        if pd.notna(company_name) and str(company_name).strip():
                            all_unmatched.add(str(company_name).strip())

                # 创建结果DataFrame: nameOfIssuer, Symbol, Source
                result_df['nameOfIssuer'] = df[name_column].copy()
                result_df['Symbol'] = tickers
                result_df['Source'] = sources

                # 生成输出文件名
                output_file = csv_file.stem + '_with_tickers.csv'

                # 保存结果
                result_df.to_csv(output_file, index=False)

                total_processed += len(df)
                total_matched += matched_count

                print(f"  ✅ 处理完成: {output_file}")
                print(f"  📊 总计 {len(df)} 条记录，成功匹配 {matched_count} 个股票代码 ({matched_count / len(df) * 100:.1f}%)")

                # 显示一些匹配示例
                matched_examples = result_df[result_df['Symbol'].notna()].head(3)
                if not matched_examples.empty:
                    print(f"  🎯 匹配示例:")
                    for _, row in matched_examples.iterrows():
                        print(f"     '{row['nameOfIssuer']}' → {row['Symbol']} ({row['Source']})")

            except Exception as e:
                print(f"  ❌ 处理文件时出错: {e}")

        # 显示总体统计
        print(f"\n" + "=" * 60)
        print(f"📈 处理完成统计:")
        print(f"   总处理记录数: {total_processed:,}")
        print(f"   成功匹配数: {total_matched:,}")
        print(f"   总体匹配率: {total_matched / total_processed * 100:.1f}%")

        # 显示一些未匹配的公司
        if all_unmatched:
            print(f"\n❓ 未匹配公司示例 (总计 {len(all_unmatched)} 家):")
            sorted_unmatched = sorted(all_unmatched)
            for i, name in enumerate(sorted_unmatched[:15]):
                print(f"   {i + 1:2d}. {name}")
            if len(all_unmatched) > 15:
                print(f"   ... 还有 {len(all_unmatched) - 15} 家未显示")

        print(f"\n💡 注意: 使用完全匹配test3.py的逻辑")
        print(f"   - 相同的数据加载逻辑")
        print(f"   - 相同的相似度计算算法")
        print(f"   - 相同的验证机制和阈值")
        print(f"   - 相同的搜索和过滤逻辑")


def check_required_files():
    """检查所需文件是否存在"""
    required_files = ["company_tickers.json", "company_tickers_exchange.json"]
    missing_files = []

    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print("❌ 缺少必需文件:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n📥 请从以下地址下载:")
        print("   - company_tickers.json: https://www.sec.gov/files/company_tickers.json")
        print("   - company_tickers_exchange.json: https://www.sec.gov/files/company_tickers_exchange.json")
        return False

    print("✅ 检测到必需的SEC文件:")
    for file in required_files:
        print(f"   - {file}")

    return True


def main():
    """主函数"""
    print("🔍 Enhanced Company Name to Ticker Tool (FIXED - 完全匹配test3.py逻辑)")
    print("=" * 60)

    # 检查必需文件
    if not check_required_files():
        return

    # 初始化转换器
    converter = EnhancedTest3TickerConverter()

    # 转换CSV文件
    converter.convert_csv_files()

    print("\n" + "=" * 60)
    print("🎉 转换完成!")
    print("\n📋 修复完成的特性:")
    print("✅ 完全使用test3.py的数据加载逻辑")
    print("✅ 完全使用test3.py的相似度计算算法")
    print("✅ 完全使用test3.py的搜索和验证逻辑")
    print("✅ 相同的阈值和过滤标准")
    print("✅ 输出格式: nameOfIssuer, Symbol, Source")
    print("✅ 数据源: local/yahoo_historical/sec_edgar_enhanced/web_search_enhanced/not_found")
    print("\n🎯 现在应该能够找到 'E M C CORP MASS' → 'EMC' 了!")


if __name__ == "__main__":
    main()