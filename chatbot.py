from groq import Groq
import os
from dotenv import load_dotenv
import json

load_dotenv()

class ComplaintChatbot:
    def __init__(self):
        """Initialize Groq client with Llama model"""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in .env file")
        
        # Initialize Groq client
        self.client = Groq(api_key=api_key)
        # Use available Groq model (llama-3.1-8b-instant is commonly available)
        self.model = "llama-3.1-8b-instant"
        self.conversation_history = []
    
    def generate_token_id(self, user_id, complaint_id):
        """Generate a unique token ID for complaint tracking"""
        import uuid
        token = f"COMP-{user_id}-{complaint_id}-{uuid.uuid4().hex[:6].upper()}"
        return token
    
    def analyze_complaint_description(self, complaint_text):
        """
        Ask detailed follow-up questions to get better description and detect emotion
        Returns: {
            'detailed_description': str,
            'emotion_state': str,
            'frustration_level': int,
            'follow_up_response': str
        }
        """
        system_prompt = """You are an empathetic complaint intake specialist. Your job is to:
1. Ask 2-3 clarifying follow-up questions to understand the complaint better
2. Detect the user's emotional state (frustrated, angry, neutral, calm)
3. Be understanding and professional

After gathering info, provide:
- Detailed complaint summary
- Emotion analysis (Calm/Neutral/Frustrated/Angry/Very Angry)
- Frustration level (1-5)

Respond in JSON format:
{
    "follow_up_questions": ["Question 1?", "Question 2?"],
    "emotion_state": "string",
    "frustration_level": 1-5,
    "needs_urgent_attention": boolean,
    "summary_request": "What specific info do you need?"
}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User's initial complaint: {complaint_text}\n\nAsk follow-up questions to better understand their issue and emotional state."}
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                max_tokens=500,
                temperature=0.7
            )
            
            response_text = chat_completion.choices[0].message.content
            
            # Try to parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "status": "success",
                    "follow_up_questions": result.get("follow_up_questions", []),
                    "emotion_state": result.get("emotion_state", "Neutral"),
                    "frustration_level": result.get("frustration_level", 2),
                    "needs_urgent_attention": result.get("needs_urgent_attention", False)
                }
        except Exception as e:
            print(f"Emotion analysis error: {e}")
        
        # Fallback response
        return {
            "status": "fallback",
            "follow_up_questions": [
                "How long has this issue been ongoing?",
                "How is this affecting you or your area?",
                "Is there any safety concern?"
            ],
            "emotion_state": "Neutral",
            "frustration_level": 2,
            "needs_urgent_attention": False
        }
    
    def chat_submit_complaint(self, user_email, complaint_text, category="Auto"):
        """Handle complaint submission via chatbot with emotion detection"""
        
        system_prompt = """You are a helpful assistant for a Smart Complaint Management System with emotion intelligence.
Your role is to:
1. Acknowledge the user's complaint with empathy
2. Ask specific follow-up questions about:
   - WHAT exactly is the problem? (specific details)
   - WHEN did it start?
   - WHERE exactly is the location?
   - HOW does it affect the user/area?
   - WHY is it urgent? (if applicable)
3. Detect emotional state based on their response
4. Show understanding of their frustration
5. Assure them action will be taken

Be professional, empathetic, and proactive. If they seem frustrated, acknowledge it and prioritize their issue."""
        
        # Build messages with system prompt included
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": complaint_text}
        ]
        
        try:
            # Use chat.completions.create for compatibility with groq 0.30.0
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                max_tokens=800,
                temperature=0.7
            )
            
            bot_response = chat_completion.choices[0].message.content
            
            # Analyze emotion from response
            emotion_analysis = self.analyze_complaint_description(complaint_text)
            
            return {
                "status": "success",
                "response": bot_response,
                "user_email": user_email,
                "complaint_text": complaint_text,
                "emotion_state": emotion_analysis.get("emotion_state", "Neutral"),
                "frustration_level": emotion_analysis.get("frustration_level", 2),
                "follow_up_questions": emotion_analysis.get("follow_up_questions", [])
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing complaint: {str(e)}"
            }
    
    def chat_check_status(self, user_email, token_id, complaint_records):
        """Handle status check via chatbot"""
        
        system_prompt = """You are a helpful customer service assistant for a Smart Complaint Management System.
Your role is to:
1. Help users check their complaint status using Token ID
2. Provide clear updates on complaint progress
3. Explain next steps in the resolution process
Be professional, empathetic, and concise."""
        
        # Find complaint by email
        matching_complaint = None
        for complaint in complaint_records:
            if complaint.get("email") == user_email:
                matching_complaint = complaint
                break
        
        if not matching_complaint:
            user_message = f"I want to check the status of my complaint (Token: {token_id})"
        else:
            user_message = f"""Please provide status for this complaint:
- Token ID: {token_id}
- Category: {matching_complaint.get('category', 'Unknown')}
- Location: {matching_complaint.get('location', 'Not specified')}
- Current Status: {matching_complaint.get('status', 'Unknown')}
- Submitted: {matching_complaint.get('created_at', 'Unknown')}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                max_tokens=500,
                temperature=0.5
            )
            
            bot_response = chat_completion.choices[0].message.content
            return {
                "status": "success",
                "response": bot_response,
                "token_id": token_id,
                "complaint_found": matching_complaint is not None
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error checking status: {str(e)}"
            }
    
    def chat_general_query(self, user_message):
        """Handle general queries about complaint system using LLM"""
        
        is_3_point_mode = user_message.startswith("3POINT: ")
        if is_3_point_mode:
            user_message = user_message[8:].strip()  # Remove "3POINT: "
        
        system_prompt = """You are a helpful AI assistant for the Smart Complaint Management System.

SYSTEM INFORMATION:
- Categories: Water Supply, Electricity, Road Infrastructure, Cleanliness, Drainage
- Status Types: Pending, Reviewing, In Progress, Resolved, Duplicate
- Features: AI-powered categorization, emotion detection, GPS location tracking, real-time status updates

Your responsibilities:
1. Answer questions about the complaint filing process
2. Explain how the system works and its features
3. Provide guidance on tracking complaints using Token ID
4. Help with general inquiries about the complaint management system
5. Answer questions about different complaint categories
6. Explain the workflow and expected resolution times

Guidelines:
- Be helpful, professional, and friendly
- Keep responses concise but informative""" + ("""
- Structure your response in exactly 3 numbered points (1. 2. 3.)""" if is_3_point_mode else "") + """
- Suggest features like GPS location pin, photo upload, and emotion-based prioritization
- Direct urgent issues to file a new complaint
- Use emojis for better user engagement
- Provide clear step-by-step guidance when needed
- Answer questions directly without referring to menus or help options"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                max_tokens=600,
                temperature=0.7
            )
            
            bot_response = chat_completion.choices[0].message.content
            return {
                "status": "success",
                "response": bot_response
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing query: {str(e)}"
            }
