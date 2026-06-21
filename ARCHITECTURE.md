# Multi-Agent Smart Trip Planning Assistant

# Software Architecture Document (SDD)

Version: 2.0

---

# 1. Project Overview

## 1.1 Purpose

The Multi-Agent Smart Trip Planning Assistant is an AI-powered travel planning system that helps users generate personalized travel itineraries using multiple specialized AI agents.

Instead of behaving like a traditional chatbot, the system acts as an intelligent planner that:

- Understands user travel requirements
- Maintains conversation context
- Coordinates multiple specialized agents
- Updates recommendations whenever user constraints change
- Explains planning decisions

The project demonstrates enterprise concepts such as:

- Multi-Agent AI
- Shared State Management
- LangGraph Orchestration
- Dynamic Replanning
- External API Integration

---

# 2. Problem Statement

Travel planning involves multiple dependent decisions.

Examples include:

- Destination selection
- Weather suitability
- Budget feasibility
- Route optimization
- Activity planning
- Itinerary generation

Changing one constraint often impacts several others.

Example:

User:

"I want to visit Goa in June."

↓

Weather analysis suggests monsoon.

↓

Water sports become unsuitable.

↓

Indoor attractions become preferred.

↓

Budget and itinerary change.

The application must automatically detect these dependencies and update the travel plan accordingly.

---

# 3. Objectives

The application should:

- Understand natural language travel requests.
- Maintain conversation context.
- Coordinate multiple AI agents.
- Share information through a common TripState.
- Dynamically decide which agents should execute.
- Replan whenever constraints change.
- Produce an explainable day-wise itinerary.

---

# 4. Technology Stack

## Language

Python 3.11

---

## Frontend

Streamlit

---

## Agent Framework

LangGraph

---

## LLM

Google Gemini 2.5 Flash

---

## Data Validation

Pydantic v2

---

## HTTP Client

Requests

---

## Environment Variables

python-dotenv

---

## External APIs

OpenWeatherMap

Visual Crossing Weather API

Geoapify Places API

OpenRouteService API

---

# 5. High-Level Architecture

```
                    User
                      │
                      ▼
               Streamlit UI
                      │
                      ▼
              LangGraph Workflow
                      │
                      ▼
               Planner Agent
                      │
      ┌───────────────┼────────────────┐
      │               │                │
      ▼               ▼                ▼
Climate Agent   Destination Agent   Budget Agent
      │               │                │
      └───────────────┼────────────────┘
                      ▼
              Transport Agent
                      │
                      ▼
              Composer Agent
                      │
                      ▼
               Final Itinerary
                      │
                      ▼
               Streamlit UI
```

---

# 6. Design Principles

## Principle 1

Planner is the only orchestrator.

Only the Planner decides which agents should execute.

---

## Principle 2

Agents never communicate directly.

All agents communicate only through the shared TripState.

---

## Principle 3

Each agent has a single responsibility.

Every agent performs exactly one business capability.

---

## Principle 4

Each agent owns its own tools.

Example

Climate Agent

↓

Weather APIs

Destination Agent

↓

Places APIs

Transport Agent

↓

Routing APIs

Budget Agent

↓

Cost Estimation Logic

---

## Principle 5

Planner never calls external APIs except Gemini for extracting user constraints.

Domain-specific APIs remain encapsulated inside their respective agents.

---

## Principle 6

TripState is the single source of truth.

Every agent:

- Reads TripState
- Updates TripState

No duplicate state exists.

---

## Principle 7

LLMs are used only where reasoning is required.

Examples

Gemini

- Constraint extraction
- Weather interpretation
- Activity reasoning
- Itinerary generation

Python

- Budget calculations
- State updates
- Agent selection
- Route processing

---

## Principle 8

Every recommendation should be explainable.

The system records important planning decisions.

Examples

- Water sports removed due to monsoon.
- Budget exceeded by ₹3,000.
- Route optimized to reduce travel time.
- Luxury hotel replaced with premium homestay.

These explanations become part of the final itinerary.

# 7. Planner Agent

## Purpose

The Planner Agent is the central coordinator of the application.

It understands the user's request, updates the shared TripState, determines which specialized agents need to execute, and coordinates the overall planning process.

The Planner does **not** perform weather analysis, budget estimation, destination recommendation, or itinerary generation itself.

Instead, it delegates these responsibilities to specialized agents.

---

## Responsibilities

The Planner performs the following steps:

### Step 1

Receive the user's message.

---

### Step 2

Use Google Gemini to extract structured trip information.

Example

User

> I want to visit Rajasthan in December with a budget of ₹40,000.

Extracted Information

- Destination
- Travel Dates
- Budget
- Travel Style
- Traveler Type
- Interests

---

### Step 3

Update the shared TripState.

Only the newly extracted information is updated.

Previously stored information remains unchanged.

---

### Step 4

Detect which fields have changed.

Example

Changed Fields

- budget
- travel_style

---

### Step 5

Determine which agents need to execute.

Examples

Destination Changed

↓

Climate

↓

Destination

↓

Transport

↓

Budget

↓

Composer

----------------------------

Budget Changed

↓

Budget

↓

Composer

----------------------------

Travel Style Changed

↓

Destination

↓

Budget

↓

Composer

---

### Step 6

Execute the selected agents one by one.

Each agent updates the shared TripState.

---

### Step 7

Invoke the Composer Agent.

The Composer generates the final itinerary.

---

### Step 8

Return the final response to the Streamlit interface.

---

# 8. Specialized Agents

The system contains five specialized agents.

Each agent has a single responsibility.

---

# 8.1 Climate Agent

## Purpose

Analyze the destination's climate during the travel period.

---

## Responsibilities

- Retrieve weather information.
- Evaluate seasonal suitability.
- Detect weather risks.
- Recommend suitable activity timings.
- Update the climate assessment.

---

## Reads

- destination
- travel_dates

---

## Writes

- climate_assessment
- decision_log

---

## APIs

- OpenWeatherMap
- Visual Crossing Weather API

---

# 8.2 Destination Agent

## Purpose

Recommend attractions and experiences based on the user's preferences.

---

## Responsibilities

- Suggest attractions.
- Recommend activities.
- Remove unsuitable activities.
- Consider weather conditions.
- Consider travel style.

---

## Reads

- destination
- traveler_type
- travel_style
- interests
- climate_assessment

---

## Writes

- recommended_experiences
- decision_log

---

## APIs

- Geoapify Places API

---

# 8.3 Transport Agent

## Purpose

Optimize travel routes between attractions.

---

## Responsibilities

- Calculate travel routes.
- Minimize unnecessary travel.
- Suggest realistic movement plans.
- Reduce travel time.

---

## Reads

- destination
- recommended_experiences

---

## Writes

- optimized_route
- decision_log

---

## APIs

- OpenRouteService API

---

# 8.4 Budget Agent

## Purpose

Evaluate whether the trip is feasible within the user's budget.

---

## Responsibilities

- Estimate overall cost.
- Compare estimated cost with budget.
- Detect budget overruns.
- Suggest alternatives when required.

---

## Reads

- budget
- travel_style
- traveler_type
- recommended_experiences
- optimized_route

---

## Writes

- budget_analysis
- decision_log

---

## Data Sources

- Local cost dataset
- Internal estimation logic

---

# 8.5 Composer Agent

## Purpose

Generate the final day-wise itinerary.

---

## Responsibilities

- Read the complete TripState.
- Organize attractions by day.
- Present recommendations clearly.
- Explain planning decisions.

---

## Reads

Entire TripState

---

## Writes

- itinerary

---

## LLM

Google Gemini

---

# 9. Shared TripState

TripState is the shared memory used by all agents.

Every agent reads from TripState and updates only the fields it owns.

---

## User Constraints

- destination
- travel_dates
- duration_days
- budget
- traveler_type
- travel_style
- interests

---

## Agent Outputs

- climate_assessment
- recommended_experiences
- optimized_route
- budget_analysis
- itinerary
- decision_log

---

## Ownership Rules

Planner

Updates

- User Constraints

Climate Agent

Updates

- climate_assessment

Destination Agent

Updates

- recommended_experiences

Transport Agent

Updates

- optimized_route

Budget Agent

Updates

- budget_analysis

Composer Agent

Updates

- itinerary

All agents may append entries to the decision_log.

---

## TripState Principles

- Single source of truth.
- Shared across all agents.
- Strongly typed using Pydantic.
- No agent stores private state.
- No agent communicates directly with another agent.