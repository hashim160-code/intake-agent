"""
Conversation state management for intake agent
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json

class ConversationStatus(Enum):
    INITIALIZING = "initializing"
    GREETING = "greeting"
    COLLECTING_INFO = "collecting_info"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class PatientInfo:
    """Patient information from database"""
    id: str
    full_name: str
    phone: str
    date_of_birth: str
    email: Optional[str] = None
    gender: Optional[str] = None

@dataclass
class TemplateInfo:
    """Template information"""
    id: str
    name: str
    questions: List[Dict]
    instructions_for_ai: str

@dataclass
class QuestionResponse:
    """Individual question and response"""
    question_id: str
    question_text: str
    response: str
    timestamp: str
    follow_up_triggered: bool = False

@dataclass
class ConversationState:
    """Main conversation state"""
    
    # Session info
    session_id: str
    intake_id: str
    room_name: str
    
    # Status tracking
    status: ConversationStatus = ConversationStatus.INITIALIZING
    current_question_index: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Data
    patient_info: Optional[PatientInfo] = None
    template_info: Optional[TemplateInfo] = None
    responses: List[QuestionResponse] = field(default_factory=list)
    
    # Metadata
    call_duration: Optional[int] = None
    retry_count: int = 0
    additional_instructions: Optional[str] = None
    
    # Audio/Recording info
    audio_file_path: Optional[str] = None
    transcript_file_path: Optional[str] = None
    
    def add_response(self, question_id: str, question_text: str, response: str, follow_up_triggered: bool = False):
        """Add a patient response to the state"""
        response_obj = QuestionResponse(
            question_id=question_id,
            question_text=question_text,
            response=response,
            timestamp=datetime.now().isoformat(),
            follow_up_triggered=follow_up_triggered
        )
        self.responses.append(response_obj)
    
    def get_current_question(self) -> Optional[Dict]:
        """Get the current question from template"""
        if not self.template_info or not self.template_info.questions:
            return None
        
        if self.current_question_index < len(self.template_info.questions):
            return self.template_info.questions[self.current_question_index]
        return None
    
    def move_to_next_question(self):
        """Move to the next question"""
        self.current_question_index += 1
    
    def is_conversation_complete(self) -> bool:
        """Check if all questions have been asked"""
        if not self.template_info:
            return False
        return self.current_question_index >= len(self.template_info.questions)
    
    def get_progress_percentage(self) -> float:
        """Get conversation progress as percentage"""
        if not self.template_info or not self.template_info.questions:
            return 0.0
        return (self.current_question_index / len(self.template_info.questions)) * 100
    
    def get_responses_summary(self) -> Dict[str, Any]:
        """Get a summary of all responses"""
        return {
            "total_questions": len(self.template_info.questions) if self.template_info else 0,
            "answered_questions": len(self.responses),
            "completion_percentage": self.get_progress_percentage(),
            "responses": [
                {
                    "question_id": r.question_id,
                    "question": r.question_text,
                    "response": r.response,
                    "timestamp": r.timestamp
                }
                for r in self.responses
            ]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for saving"""
        return {
            "session_id": self.session_id,
            "intake_id": self.intake_id,
            "room_name": self.room_name,
            "status": self.status.value,
            "current_question_index": self.current_question_index,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "patient_info": {
                "id": self.patient_info.id,
                "full_name": self.patient_info.full_name,
                "phone": self.patient_info.phone,
                "date_of_birth": self.patient_info.date_of_birth,
                "email": self.patient_info.email,
                "gender": self.patient_info.gender
            } if self.patient_info else None,
            "template_info": {
                "id": self.template_info.id,
                "name": self.template_info.name,
                "questions": self.template_info.questions,
                "instructions_for_ai": self.template_info.instructions_for_ai
            } if self.template_info else None,
            "responses": [
                {
                    "question_id": r.question_id,
                    "question_text": r.question_text,
                    "response": r.response,
                    "timestamp": r.timestamp,
                    "follow_up_triggered": r.follow_up_triggered
                }
                for r in self.responses
            ],
            "call_duration": self.call_duration,
            "retry_count": self.retry_count,
            "additional_instructions": self.additional_instructions,
            "audio_file_path": self.audio_file_path,
            "transcript_file_path": self.transcript_file_path
        }

class StateManager:
    """Manages conversation state across the session"""
    
    def __init__(self):
        self.current_state: Optional[ConversationState] = None
    
    def initialize_state(self, session_id: str, intake_id: str, room_name: str, 
                        patient_info: PatientInfo, template_info: TemplateInfo) -> ConversationState:
        """Initialize a new conversation state"""
        self.current_state = ConversationState(
            session_id=session_id,
            intake_id=intake_id,
            room_name=room_name,
            patient_info=patient_info,
            template_info=template_info,
            status=ConversationStatus.GREETING
        )
        return self.current_state
    
    def get_current_state(self) -> Optional[ConversationState]:
        """Get the current conversation state"""
        return self.current_state
    
    def update_status(self, status: ConversationStatus):
        """Update conversation status"""
        if self.current_state:
            self.current_state.status = status
    
    def save_state_to_file(self, file_path: str):
        """Save current state to JSON file"""
        if self.current_state:
            with open(file_path, 'w') as f:
                json.dump(self.current_state.to_dict(), f, indent=2)
    
    def load_state_from_file(self, file_path: str) -> ConversationState:
        """Load state from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Reconstruct the state object
        # (You'd need to implement the from_dict method)
        return self._from_dict(data)