"""
Predefined intake templates
"""

# This matches your database schema for the templates table
PREDEFINED_TEMPLATES = {
    "general_intake": {
        "template_name": "General Intake Template",
        "template_type": "intake",
        "structure": "standard_medical_intake",
        "instructions_for_ai": "Follow standard medical intake protocol. Be thorough but efficient.",
        "questions": [
            {
                "id": "q1",
                "question_text": "Can you please confirm your full name and date of birth?",
                "question_type": "text",
                "required": True,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q2", 
                "question_text": "What is the main reason for your visit today?",
                "question_type": "text",
                "required": True,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q3",
                "question_text": "Are you currently taking any medications?",
                "question_type": "yes_no",
                "required": True,
                "follow_up_questions": ["q3a"],
                "validation_rules": None
            },
            {
                "id": "q3a",
                "question_text": "Please list all medications you are currently taking, including dosages.",
                "question_type": "text", 
                "required": False,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q4",
                "question_text": "Do you have any known allergies?",
                "question_type": "yes_no",
                "required": True,
                "follow_up_questions": ["q4a"],
                "validation_rules": None
            },
            {
                "id": "q4a",
                "question_text": "Please describe your allergies and any reactions you've had.",
                "question_type": "text",
                "required": False,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q5",
                "question_text": "Have you had any recent surgeries or hospitalizations?",
                "question_type": "yes_no",
                "required": True,
                "follow_up_questions": ["q5a"],
                "validation_rules": None
            },
            {
                "id": "q5a",
                "question_text": "Please provide details about your recent surgeries or hospitalizations.",
                "question_type": "text",
                "required": False,
                "follow_up_questions": None,
                "validation_rules": None
            }
        ]
    },
    
    "cardiology_intake": {
        "template_name": "Cardiology Intake Template", 
        "template_type": "intake",
        "structure": "cardiology_specialized",
        "instructions_for_ai": "Focus on cardiovascular symptoms and history. Be thorough about heart-related questions.",
        "questions": [
            {
                "id": "q1",
                "question_text": "Can you please confirm your full name and date of birth?",
                "question_type": "text",
                "required": True,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q2",
                "question_text": "What brings you in for your cardiology appointment today?",
                "question_type": "text",
                "required": True,
                "follow_up_questions": None,
                "validation_rules": None
            },
            {
                "id": "q3",
                "question_text": "Do you experience chest pain or discomfort?",
                "question_type": "yes_no",
                "required": True,
                "follow_up_questions": ["q3a", "q3b"],
                "validation_rules": None
            },
            {
                "id": "q3a",
                "question_text": "When do you experience chest pain?",
                "question_type": "multiple_choice",
                "required": False,
                "follow_up_questions": None,
                "validation_rules": {
                    "choices": ["During exercise", "At rest", "When lying down", "After eating", "Other"]
                }
            },
            {
                "id": "q3b",
                "question_text": "On a scale of 1-10, how would you rate your chest pain?",
                "question_type": "scale",
                "required": False,
                "follow_up_questions": None,
                "validation_rules": {
                    "min": 1,
                    "max": 10
                }
            }
            # ... more cardiology-specific questions
        ]
    }
}

def get_predefined_template(template_name: str):
    """Get a predefined template by name"""
    return PREDEFINED_TEMPLATES.get(template_name)

def list_available_templates():
    """List all available predefined templates"""
    return list(PREDEFINED_TEMPLATES.keys())

def get_template_questions(template_name: str):
    """Get just the questions from a template"""
    template = get_predefined_template(template_name)
    return template['questions'] if template else []