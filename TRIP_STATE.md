# TripState Specification

Version: 1.0

---

# Purpose

TripState is the single shared state object used by all agents in the LangGraph workflow.

It represents the complete business state of the trip planning process.

Every agent reads from TripState and writes back to TripState.

TripState is the only communication mechanism between agents.

Planner runtime information (such as execution queues) is intentionally excluded from TripState.

---

# Design Principles

1. Single Source of Truth

TripState contains the latest validated state of the trip.

---

2. Shared State

Agents never communicate directly.

Agents communicate only through TripState.

---

3. Business State Only

TripState stores business information.

It does NOT store Planner runtime information.

---

4. Strong Typing

All complex outputs use dedicated Pydantic models.

Generic dictionaries are not allowed.

---

# Structure

TripState consists of three logical sections.

```
TripState

├── User Constraints

├── Agent Outputs

└── Decision Log
```

---

# User Constraints

These fields represent information provided directly or indirectly by the user.

---

## destination

Type

string

Required

No

Updated By

Planner

Read By

Climate Agent

Destination Agent

Transport Agent

Budget Agent

Composer Agent

Description

Primary travel destination.

---

## travel_dates

Type

DateRange

Required

No

Updated By

Planner

Read By

Climate Agent

Transport Agent

Budget Agent

Composer Agent

Description

Start and end dates of the trip.

---

## duration_days

Type

integer

Required

No

Updated By

Planner

Read By

Destination Agent

Budget Agent

Composer Agent

Description

Total trip duration.

---

## budget

Type

float

Required

No

Updated By

Planner

Read By

Budget Agent

Destination Agent

Composer Agent

Description

Maximum user budget.

---

## traveler_type

Type

TravelerType

Required

No

Updated By

Planner

Read By

Destination Agent

Budget Agent

Composer Agent

Description

Type of travellers.

Possible values

- Solo

- Couple

- Family

- Friends

---

## travel_style

Type

TravelStyle

Required

No

Updated By

Planner

Read By

Destination Agent

Budget Agent

Composer Agent

Description

Preferred travel style.

Possible values

- Budget

- Mid-range

- Luxury

---

## interests

Type

List[str]

Required

No

Updated By

Planner

Read By

Destination Agent

Composer Agent

Description

Activities preferred by the user.

Example

- Beaches

- Trekking

- Museums

- Food

- Adventure

---

# Agent Outputs

---

## climate_assessment

Type

ClimateAssessment

Updated By

Climate Agent

Read By

Destination Agent

Transport Agent

Composer Agent

Description

Seasonal weather analysis and recommendations.

---

## recommended_experiences

Type

List[Experience]

Updated By

Destination Agent

Read By

Transport Agent

Budget Agent

Composer Agent

Description

Recommended attractions and activities.

---

## optimized_route

Type

RoutePlan

Updated By

Transport Agent

Read By

Budget Agent

Composer Agent

Description

Optimized travel route.

---

## budget_analysis

Type

BudgetAnalysis

Updated By

Budget Agent

Read By

Destination Agent

Composer Agent

Description

Budget feasibility and optimization suggestions.

---

## itinerary

Type

string

Updated By

Composer Agent

Read By

Streamlit UI

Description

Final formatted itinerary.

---

# Decision Log

## decision_log

Type

List[str]

Updated By

All Agents

Read By

Composer Agent

Streamlit UI

Description

Stores important planning decisions.

Examples

- Water sports removed due to monsoon.

- Budget exceeded by ₹4,500.

- Luxury hotel replaced with premium homestay.

- Route optimized to reduce travel time.

- Outdoor activities shifted to morning.

The decision log enables explainable AI.

---

# Constraint Updates

TripState is never modified directly.

Instead,

the Planner first creates a ConstraintUpdate object.

```
User

↓

Constraint Parser

↓

ConstraintUpdate

↓

State Manager

↓

TripState
```

Only the State Manager is responsible for merging updates into TripState.

---

# Ownership Rules

Planner

Updates

- User Constraints

Reads

Entire TripState

---

Climate Agent

Reads

Destination

Travel Dates

Writes

Climate Assessment

---

Destination Agent

Reads

Destination

Travel Style

Traveler Type

Duration

Interests

Climate Assessment

Budget Analysis

Writes

Recommended Experiences

Decision Log

---

Transport Agent

Reads

Recommended Experiences

Travel Dates

Writes

Optimized Route

Decision Log

---

Budget Agent

Reads

Budget

Travel Style

Traveler Type

Recommended Experiences

Optimized Route

Writes

Budget Analysis

Decision Log

---

Composer Agent

Reads

Entire TripState

Writes

Final Itinerary

Decision Log

---

# Validation Rules

All fields must be validated using Pydantic.

Null values are allowed until the Planner receives the corresponding information from the user.

No field may be represented using Dict[str, Any].

All nested structures must use dedicated Pydantic models.

---


# ConstraintUpdate Specification

## Purpose

ConstraintUpdate represents a partial update to the current TripState.

Unlike TripState, which always represents the complete shared business state, ConstraintUpdate contains only the fields extracted from the user's most recent message.

This model is created by the Constraint Parser and consumed by the State Manager.

---

## Why It Exists

Users rarely provide all trip information in a single message.

Example

User:

> I want to visit Goa.

↓

ConstraintUpdate

```
destination = "Goa"
```

---

User:

> Make it a budget trip.

↓

ConstraintUpdate

```
travel_style = Budget
```

---

User:

> Increase my budget to ₹50,000.

↓

ConstraintUpdate

```
budget = 50000
```

Only the newly extracted information is returned.

Existing values remain unchanged inside TripState.

---

## Workflow

```
User Message
       │
       ▼
Constraint Parser
       │
       ▼
ConstraintUpdate
       │
       ▼
State Manager
       │
       ▼
TripState
```

The State Manager is the only component responsible for merging ConstraintUpdate into TripState.

---

## Rules

1. Every field in ConstraintUpdate is optional.

2. ConstraintUpdate never represents the complete application state.

3. ConstraintUpdate is immutable after validation.

4. ConstraintUpdate is never shared between agents.

5. ConstraintUpdate exists only during the Planner execution cycle.

6. ConstraintUpdate is discarded after the State Manager updates TripState.

---

## Supported Fields

ConstraintUpdate may contain any subset of the following fields:

- destination
- travel_dates
- duration_days
- budget
- traveler_type
- travel_style
- interests

If a field is absent, the Planner assumes that the user did not modify that constraint.

---

## Example

Current TripState

```
Destination: Goa
Budget: ₹40,000
Travel Style: Budget
```

User

> Make it a luxury trip with ₹60,000.

ConstraintUpdate

```
travel_style = Luxury

budget = 60000
```

State Manager

↓

Updated TripState

```
Destination: Goa

Budget: ₹60,000

Travel Style: Luxury
```

Notice that the destination remains unchanged because it was not included in the ConstraintUpdate.

---

## Benefits

Using ConstraintUpdate provides several advantages:

- Supports incremental conversations.
- Eliminates unnecessary state reconstruction.
- Simplifies change detection.
- Reduces data duplication.
- Enables efficient replanning.
- Keeps Planner logic clean and deterministic.

---

# PlannerContext Specification

## Purpose

PlannerContext stores the Planner's runtime execution state.

Unlike TripState, which represents the shared business state of the application, PlannerContext exists only during a single planning cycle.

PlannerContext is **never shared with agents**.

Only the Planner reads from and writes to PlannerContext.

---

## Why It Exists

TripState should contain only business information.

The Planner, however, requires additional runtime information while orchestrating the workflow.

Examples include:

- Which fields changed
- Which agents still need execution
- Which agent is currently running
- Which agents have already completed

These values are orchestration details rather than business data.

Keeping them inside PlannerContext keeps TripState clean and independent.

---

## Workflow

```
                 User
                   │
                   ▼
          Constraint Parser
                   │
                   ▼
          ConstraintUpdate
                   │
                   ▼
            PlannerContext
                   │
                   ▼
            State Manager
                   │
                   ▼
               TripState
                   │
                   ▼
        Dependency Resolver
                   │
                   ▼
           Execution Queue
                   │
                   ▼
                 Agents
```

---

## PlannerContext Fields

### constraint_update

Type

ConstraintUpdate

Description

Contains the latest structured information extracted from the user's message.

Updated By

Constraint Parser

Read By

State Manager

---

### changed_fields

Type

List[str]

Description

Stores the fields that were modified after merging ConstraintUpdate into TripState.

Example

```
[
    "budget",
    "travel_style"
]
```

Updated By

State Manager

Read By

Dependency Resolver

---

### pending_agents

Type

Deque[AgentName]

Description

Execution queue maintained by the Planner.

Contains agents waiting for execution.

Updated By

Dependency Resolver

Read By

Planner

---

### completed_agents

Type

List[AgentName]

Description

Stores agents already executed during the current planning cycle.

Updated By

Planner

Read By

Planner

---

### current_agent

Type

AgentName | None

Description

The agent currently being executed.

Updated By

Planner

---

### execution_cycle

Type

Integer

Description

Current replanning iteration.

Starts from 1.

Increments whenever dependency resolution schedules another execution cycle.

---

### planner_notes

Type

List[str]

Description

Internal Planner observations.

These notes are **not** shown to the user.

Examples

- Budget changed.
- Destination unchanged.
- Replanning required.
- Queue rebuilt.

---

## Lifetime

PlannerContext exists only during one execution cycle.

After the final itinerary is produced, PlannerContext is discarded.

Only TripState persists throughout the conversation.

---

## Ownership Rules

Only the Planner may create, modify, or destroy PlannerContext.

No agent may access PlannerContext.

Agents interact exclusively through TripState.

---

## Benefits

Separating PlannerContext from TripState provides several advantages:

- Keeps business state independent from orchestration logic.
- Prevents agents from accessing internal Planner information.
- Simplifies testing of the Planner.
- Makes the architecture extensible.
- Follows the Single Responsibility Principle.
- Aligns with enterprise workflow orchestration patterns.

---

# Summary

TripState is the single shared business state of the application.

It is:

- Shared by all agents
- Strongly typed
- Incrementally updated
- Independent of Planner runtime logic
- The single source of truth throughout the LangGraph workflow