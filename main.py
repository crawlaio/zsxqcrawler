import re
from urllib import parse

import pangu
import requests
from loguru import logger
from pyquery import PyQuery
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class ZsxqSpider(object):
    def __init__(self):
        # self.group_id = "152********812"
        # self.cookies = {
        #     "UM_distinctid": "********",
        #     "abtest_env": "product",
        #     "zsxq_access_token": "********",
        #     "sensorsdata2015jssdkcross": "********",
        # }
        self.group_id = "88512428581812"
        self.cookies = {
            'UM_distinctid': '1739fb0c72a48d-0cb68d0f731622-31677305-1ea000-1739fb0c72bf18',
            'abtest_env': 'product',
            'zsxq_access_token': '3FDC1F86-784C-FA56-FA61-A6982F85A4B5_DCB1ECD2A5B8202E',
            'sensorsdata2015jssdkcross': '%7B%22distinct_id%22%3A%221739fb37f8e2c-0801e419f76d5e-31677305-2007040-1739fb37f8f968%22%2C%22%24device_id%22%3A%221739fb37f8e2c-0801e419f76d5e-31677305-2007040-1739fb37f8f968%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_referrer%22%3A%22%22%2C%22%24latest_referrer_host%22%3A%22%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%7D%7D',
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9,und;q=0.8,en;q=0.7",
        }
        self.base_url = f"https://api.zsxq.com/v1.10/groups/{self.group_id}/topics"
        self.end_time = "0"
        self.latest_time = None
        self.params = {
            "scope": "all",
            "count": "20",
            "end_time": self.end_time,
        }
        self.data = dict()
        self.md_list = []
        self.count = 0

    def crawler(self):
        self.params["end_time"] = self.end_time
        response = requests.get(
            url=self.base_url, headers=self.headers, cookies=self.cookies, verify=False, params=self.params
        )
        self.data = response.json()
        if self.data.get("succeeded"):
            return True
        else:
            logger.error(f"Crawler Group: {self.group_id} error!")
            return False

    def parse_topics(self):
        topics = self.data.get("resp_data", {}).get("topics", [])
        if topics:
            self.end_time = topics[-1].get("create_time")
        if self.end_time != self.latest_time:
            self.latest_time = self.end_time
        else:
            logger.info(f"Crawler Group: {self.group_id} finished!")
            return False
        self.count += len(topics)
        for topic in topics:
            md = []
            topic_type = topic.get("type")
            md.append(self.parse_header(topic))
            if topic_type == "talk":
                md += self.parse_talk(topic)
            elif topic_type == "q&a":
                md += self.parse_qa(topic)
            else:
                self.count -= 1
                continue
            md.append(self.parse_comment(topic))
            md_text = "\n".join(md)
            self.md_list.append(md_text)
        logger.info(f"Crawler Group: {self.group_id} {self.count} count!")
        return True

    @staticmethod
    def parse_html(content):
        content = content.replace("\n", "<br>")
        result = re.findall(r"<e [^>]*>", content)
        if result:
            for i in result:
                html = PyQuery(i)
                if html.attr("type") == "web":
                    template = "[%s](%s)" % (parse.unquote(html.attr("title")), parse.unquote(html.attr("href")))
                elif html.attr("type") == "hashtag":
                    template = " `%s` " % parse.unquote(html.attr("title"))
                elif html.attr("type") == "mention":
                    template = parse.unquote(html.attr("title"))
                else:
                    template = i
                content = content.strip().replace(i, template)
        else:
            content = pangu.spacing_text(content)
        return content

    @staticmethod
    def parse_header(topic):
        data_time = topic["create_time"]
        group = topic.get("group", {}).get("name")
        return f"# {group} - {data_time.split('T')[0]}"

    def parse_comment(self, topic):
        comments = [
            comment.get("owner").get("name") + ": " + self.parse_html(comment.get("text", ""))
            for comment in topic.get("show_comments", [])
        ]
        comment_text = "```\n" + "\n".join(comments) + "\n```" if comments else ""
        return comment_text

    def parse_qa(self, topic):
        question_text = self.parse_html(topic.get("question", {}).get("text", ""))
        answer_text = self.parse_html(topic.get("answer", {}).get("text", ""))
        question_images = []
        if topic.get("question").get("images"):
            for img in topic.get("question").get("images"):
                url = img.get("large").get("url")
                question_images.append(url)
        answer_images = []
        if topic.get("answer").get("images"):
            for img in topic.get("answer").get("images"):
                url = img.get("large").get("url")
                answer_images.append(url)

        question_image_text = "\n".join([f"![]({question_image})" for question_image in question_images])
        answer_image_text = "\n".join([f"![]({answer_image})" for answer_image in answer_images])
        md = ["## Question:", question_text, question_image_text, "## Answer:", answer_text, answer_image_text]
        return md

    def parse_talk(self, topic):
        content = self.parse_html(topic.get("talk", {}).get("text", ""))
        images = []
        if topic.get("talk").get("images"):
            for img in topic.get("talk").get("images"):
                url = img.get("large").get("url")
                images.append(url)

        image_text = "\n".join([f"![]({image})" for image in images])
        md = [content, image_text]
        return md

    def run(self):
        while True:
            if not self.crawler():
                break
            if not self.parse_topics():
                break
        text = "\n".join(self.md_list[::-1])
        logger.info(f"Writing into {self.group_id}.md")
        with open(f"data/{self.group_id}.md", "w") as f:
            f.write(text)
        logger.info(f"Crawler {self.group_id} Finished, Count: {self.count}")


if __name__ == "__main__":
    zsxq = ZsxqSpider()
    zsxq.run()
