# nlp_tools.py
# Natural Language Processing module - Integrating NLTK, regex, and advanced text processing
# Provides text analysis, sentiment analysis, entity extraction, and more

import re
from typing import List, Dict, Tuple, Optional
import warnings

# Lazy imports to avoid startup overhead
def load_nltk():
    """Load NLTK on demand"""
    try:
        import nltk
        return nltk
    except ImportError:
        print("⚠️  NLTK not available. Install with: pip install nltk")
        return None

def load_regex():
    """Load regex on demand"""
    try:
        import regex
        return regex
    except ImportError:
        print("⚠️  regex not available. Using standard re module")
        return None

class NLPAnalyzer:
    """Comprehensive NLP analysis using NLTK and regex"""
    
    def __init__(self):
        self.nltk = load_nltk()
        self.regex = load_regex()
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words"""
        if self.nltk is None:
            # Fallback to basic tokenization
            return re.findall(r'\b\w+\b', text.lower())
        
        try:
            from nltk.tokenize import word_tokenize
            return word_tokenize(text)
        except:
            return re.findall(r'\b\w+\b', text.lower())
    
    def sentence_tokenize(self, text: str) -> List[str]:
        """Split text into sentences"""
        if self.nltk is None:
            return re.split(r'[.!?]+', text)
        
        try:
            from nltk.tokenize import sent_tokenize
            return sent_tokenize(text)
        except:
            return re.split(r'[.!?]+', text)
    
    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        """Remove common stopwords"""
        if self.nltk is None:
            common_stopwords = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been'
            }
            return [t for t in tokens if t.lower() not in common_stopwords]
        
        try:
            from nltk.corpus import stopwords
            stop_words = set(stopwords.words('english'))
            return [t for t in tokens if t.lower() not in stop_words]
        except:
            return tokens
    
    def pos_tagging(self, tokens: List[str]) -> List[Tuple[str, str]]:
        """Part-of-speech tagging"""
        if self.nltk is None:
            return [(token, 'NN') for token in tokens]
        
        try:
            from nltk import pos_tag
            return pos_tag(tokens)
        except:
            return [(token, 'NN') for token in tokens]
    
    def named_entity_recognition(self, text: str) -> List[Tuple[str, str]]:
        """Extract named entities from text"""
        if self.nltk is None:
            # Basic regex-based entity extraction
            entities = []
            # Find capitalized words (potential proper nouns)
            for word in re.findall(r'\b[A-Z][a-z]+\b', text):
                entities.append((word, 'PROPER_NOUN'))
            return entities
        
        try:
            from nltk import ne_chunk, pos_tag, word_tokenize
            tokens = word_tokenize(text)
            tagged = pos_tag(tokens)
            tree = ne_chunk(tagged)
            
            entities = []
            for subtree in tree:
                if hasattr(subtree, 'label'):
                    entity_name = ' '.join(word for word, tag in subtree.leaves())
                    entities.append((entity_name, subtree.label()))
            return entities
        except:
            return []
    
    def sentiment_analysis(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text (positive/negative/neutral)"""
        try:
            from nltk.sentiment import SentimentIntensityAnalyzer
            sia = SentimentIntensityAnalyzer()
            scores = sia.polarity_scores(text)
            return {
                'negative': scores['neg'],
                'neutral': scores['neu'],
                'positive': scores['pos'],
                'compound': scores['compound']
            }
        except:
            # Fallback: simple keyword matching
            positive_words = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic'}
            negative_words = {'bad', 'poor', 'terrible', 'awful', 'horrible', 'hate'}
            
            words = set(text.lower().split())
            pos_count = len(words & positive_words)
            neg_count = len(words & negative_words)
            total = pos_count + neg_count
            
            if total == 0:
                return {'positive': 0, 'negative': 0, 'neutral': 1.0, 'compound': 0}
            
            return {
                'positive': pos_count / total,
                'negative': neg_count / total,
                'neutral': 0,
                'compound': (pos_count - neg_count) / total
            }
    
    def extract_keywords(self, text: str, num_keywords: int = 5) -> List[Tuple[str, float]]:
        """Extract most important keywords using TF-IDF approach"""
        tokens = self.tokenize(text)
        tokens = self.remove_stopwords(tokens)
        
        # Simple frequency-based extraction
        from collections import Counter
        freq = Counter(tokens)
        return freq.most_common(num_keywords)
    
    def text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)"""
        tokens1 = set(self.tokenize(text1.lower()))
        tokens2 = set(self.tokenize(text2.lower()))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0
    
    def spell_check(self, text: str) -> Dict[str, List[str]]:
        """Basic spell checking and suggestions"""
        try:
            from nltk.corpus import words
            valid_words = set(words.words())
        except:
            valid_words = set()
        
        tokens = self.tokenize(text)
        errors = {}
        
        for token in tokens:
            if token.lower() not in valid_words and token.isalpha():
                # Generate simple suggestions (first letters match)
                suggestions = [t for t in valid_words if t.startswith(token[0]) and len(t) == len(token)]
                if suggestions:
                    errors[token] = suggestions[:3]
        
        return errors


class RegexTools:
    """Advanced regex pattern matching utilities"""
    
    def __init__(self):
        self.regex = load_regex()
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses"""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        if self.regex:
            return self.regex.findall(pattern, text)
        return re.findall(pattern, text)
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs"""
        pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        if self.regex:
            return self.regex.findall(pattern, text)
        return re.findall(pattern, text)
    
    def extract_phone_numbers(self, text: str) -> List[str]:
        """Extract phone numbers"""
        pattern = r'(?:\+\d{1,3})?[-.\s]?\(?(?:\d{2,3})\)?[-.\s]?\d{3,4}[-.\s]?\d{4}'
        if self.regex:
            return self.regex.findall(pattern, text)
        return re.findall(pattern, text)
    
    def extract_dates(self, text: str) -> List[str]:
        """Extract dates in various formats"""
        pattern = r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}'
        if self.regex:
            return self.regex.findall(pattern, text)
        return re.findall(pattern, text)
    
    def fuzzy_match(self, pattern: str, text: str) -> List[Tuple[str, float]]:
        """Fuzzy regex matching (if regex library available)"""
        if not self.regex:
            # Fallback to exact matching
            matches = re.findall(pattern, text)
            return [(m, 1.0) for m in matches]
        
        try:
            matches = self.regex.finditer(pattern, text, flags=self.regex.FUZZY)
            return [(m.group(), m.fuzzy_counts[0]/100) for m in matches]
        except:
            return []


class TextSummarizer:
    """Text summarization using extractive methods"""
    
    def __init__(self):
        self.nlp = NLPAnalyzer()
    
    def summarize(self, text: str, num_sentences: int = 3) -> str:
        """Extract key sentences to summarize text"""
        sentences = self.nlp.sentence_tokenize(text)
        
        if len(sentences) <= num_sentences:
            return text
        
        # Score sentences based on keyword frequency
        words = self.nlp.tokenize(text)
        words = self.nlp.remove_stopwords(words)
        
        from collections import Counter
        word_freq = Counter(words)
        
        sentence_scores = {}
        for i, sentence in enumerate(sentences):
            for word in self.nlp.tokenize(sentence):
                if word in word_freq:
                    sentence_scores[i] = sentence_scores.get(i, 0) + word_freq[word]
        
        # Get top sentences in order
        top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:num_sentences]
        top_sentences = sorted(top_sentences, key=lambda x: x[0])  # Restore original order
        
        summary = ' '.join([sentences[i] for i, _ in top_sentences])
        return summary


# ===== MAIN NLP FUNCTIONS =====

def analyze_text(text: str) -> Dict:
    """Complete text analysis"""
    analyzer = NLPAnalyzer()
    
    return {
        'original': text,
        'tokens': analyzer.tokenize(text),
        'sentences': analyzer.sentence_tokenize(text),
        'keywords': analyzer.extract_keywords(text, 5),
        'sentiment': analyzer.sentiment_analysis(text),
        'entities': analyzer.named_entity_recognition(text),
        'length': len(text)
    }

def extract_information(text: str) -> Dict:
    """Extract structured information from text"""
    regex_tools = RegexTools()
    
    return {
        'emails': regex_tools.extract_emails(text),
        'urls': regex_tools.extract_urls(text),
        'phones': regex_tools.extract_phone_numbers(text),
        'dates': regex_tools.extract_dates(text)
    }

def summarize_text(text: str, num_sentences: int = 3) -> str:
    """Summarize text"""
    summarizer = TextSummarizer()
    return summarizer.summarize(text, num_sentences)


# ===== TESTING =====

if __name__ == "__main__":
    print("\n" + "🔤 NLP TOOLS TEST SUITE 🔤".center(70))
    print("="*70 + "\n")
    
    # Sample text
    sample_text = """
    Natural Language Processing is amazing! It helps computers understand human language.
    You can extract emails like test@example.com or visit https://www.example.com.
    Contact us at +1-234-567-8900. This is great technology!
    """
    
    # Test 1: Text analysis
    print("Test 1: Text Analysis")
    print("-" * 70)
    analysis = analyze_text(sample_text)
    print(f"Tokens: {analysis['tokens'][:5]}...")
    print(f"Sentiment: {analysis['sentiment']}")
    print(f"Keywords: {analysis['keywords']}")
    print()
    
    # Test 2: Information extraction
    print("Test 2: Information Extraction")
    print("-" * 70)
    info = extract_information(sample_text)
    print(f"Emails: {info['emails']}")
    print(f"URLs: {info['urls']}")
    print(f"Phones: {info['phones']}")
    print()
    
    # Test 3: Text summarization
    print("Test 3: Text Summarization")
    print("-" * 70)
    summary = summarize_text(sample_text, 2)
    print(f"Summary: {summary}")
    print()
    
    print("="*70)
    print("✅ NLP TESTS COMPLETED".center(70))
    print("="*70 + "\n")
