"""
LLM-based Complaint Classifier with Emotion Detection
Uses Groq API for fast inference
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class ComplaintClassifier:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "mixtral-8x7b-32768"
        
    def classify_complaint(self, complaint_text: str) -> dict:
        """
        Classify complaint and detect emotion using LLM
        Returns: {
            'category': str,
            'confidence': float,
            'emotion_state': str,
            'frustration_level': int (1-5),
            'reasoning': str
        }
        """
        
        prompt = f"""You are an expert complaint classifier. Analyze the following complaint and provide:
1. Category (must be one of: Road, Water, Electricity, Cleanliness, Drainage, Other)
2. User's emotional state (Calm, Neutral, Frustrated, Angry, Very Angry)
3. Frustration level (1-5, where 1=calm, 5=extremely angry)
4. Brief reasoning

Complaint: "{complaint_text}"

IMPORTANT: Respond in JSON format ONLY:
{{
    "category": "string",
    "confidence": 0.95,
    "emotion_state": "string",
    "frustration_level": 3,
    "reasoning": "string"
}}

Use these signs to detect frustration:
- Excessive punctuation (!!!), CAPS LOCK
- Negative words: problem, issue, terrible, worst, urgent, immediately
- Repeated complaints or urgency
- Explicit frustration indicators: frustrated, angry, upset, furious
"""

        try:
            message = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            response_text = message.choices[0].message.content
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'category': result.get('category', 'Other'),
                    'confidence': result.get('confidence', 0.8),
                    'emotion_state': result.get('emotion_state', 'Neutral'),
                    'frustration_level': result.get('frustration_level', 2),
                    'reasoning': result.get('reasoning', 'LLM classified')
                }
        except Exception as e:
            print(f"LLM Classification Error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
        
        # Fallback: Simple rule-based detection
        print("Using fallback rule-based classification...")
        return self._fallback_classify(complaint_text)
    
    def _fallback_classify(self, complaint_text: str) -> dict:
        """Fallback to rule-based classification if LLM fails"""
        text_lower = complaint_text.lower()
        
        # Category detection
        categories = {
            'Road': ['road', 'pothole', 'broken', 'asphalt', 'pavement', 'street'],
            'Water': ['water', 'tap', 'supply', 'dirty', 'leak', 'pipeline'],
            'Electricity': ['electricity', 'power', 'light', 'pole', 'electric', 'wire'],
            'Drainage': ['drain', 'sewer', 'blocked', 'overflow', 'stagnation'],
            'Cleanliness': ['garbage', 'dustbin', 'waste', 'clean', 'smell']
        }
        
        category = 'Other'
        for cat, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                category = cat
                break
        
        # Emotion detection
        frustration_indicators = ['!!!', '!!', 'URGENT', 'IMMEDIATE', 'TERRIBLE', 'WORST']
        emotion_words = {
            'Very Angry': ['furious', 'extremely upset', 'very angry', 'livid'],
            'Angry': ['angry', 'upset', 'disgusted'],
            'Frustrated': ['frustrated', 'irritated', 'annoyed', 'problem', 'issue'],
            'Neutral': ['please', 'kindly', 'could you'],
            'Calm': ['thank you', 'appreciate', 'grateful']
        }
        
        frustration_level = 2
        emotion_state = 'Neutral'
        
        for state, keywords in emotion_words.items():
            if any(word in text_lower for word in keywords):
                emotion_state = state
                if state == 'Very Angry':
                    frustration_level = 5
                elif state == 'Angry':
                    frustration_level = 4
                elif state == 'Frustrated':
                    frustration_level = 3
                break
        
        # Count caps and punctuation
        caps_ratio = sum(1 for c in complaint_text if c.isupper()) / max(len(complaint_text), 1)
        exclamation_count = complaint_text.count('!')
        
        if caps_ratio > 0.3 or exclamation_count >= 3:
            frustration_level = min(5, frustration_level + 1)
            if emotion_state == 'Neutral':
                emotion_state = 'Frustrated'
        
        return {
            'category': category,
            'confidence': 0.7,
            'emotion_state': emotion_state,
            'frustration_level': frustration_level,
            'reasoning': 'Fallback rule-based classification'
        }


# Initialize globally
classifier = None

def get_classifier():
    global classifier
    if classifier is None:
        classifier = ComplaintClassifier()
    return classifier


def classify_complaint(text: str) -> dict:
    """Public function to classify a complaint"""
    clf = get_classifier()
    return clf.classify_complaint(text)
