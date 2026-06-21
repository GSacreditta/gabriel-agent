# Gabriel Agent - Product Requirements Document (PRD)

## 1. Product Overview
Gabriel Agent is an AI-powered personal assistant designed to manage structured tasks, reminders, and file-based workflows. The system leverages advanced AI capabilities to process documents, organize information, and provide intelligent task management. The agent uses LangChain, FAISS for vector storage, and OpenAI to create a powerful document processing and task management system. The primary interface is through Slack, which serves both as the user interface and the Human-Device Interface (HDI).

## 2. Target Users
- Professionals managing multiple documents and tasks
- Users requiring automated document processing
- Individuals seeking intelligent task organization
- Teams needing workflow automation
- Financial analysts processing investment reports
- Researchers managing large document collections

## 3. Core Features

### 3.1 Document Processing
- PDF investment report analysis
- Text extraction and summarization
- Key information identification
- Document metadata extraction
- Support for multiple document formats
- OCR capabilities for scanned documents
- Document similarity analysis
- Automated document categorization
- Document relationship mapping
- Content-based search and retrieval
- Vector embeddings storage in FAISS
- Document chunking and processing

### 3.2 File Organization
- Automatic folder structure creation
- Smart file categorization
- Metadata-based organization
- Custom organization rules
- File relationship mapping
- Version control integration
- Backup and recovery options
- Storage optimization
- File access control
- Automated cleanup routines
- Google Drive integration

### 3.3 Task Management
- Task creation and tracking
- Priority-based organization
- Deadline management
- Task dependencies
- Progress tracking
- Automated task summarization
- Task templates and workflows
- Recurring task management
- Task delegation capabilities
- Task analytics and reporting

### 3.4 User Interface
- Slack-based chat interface
- Interactive command processing
- Status reporting
- Progress visualization
- Error handling and feedback
- Custom command aliases
- Interactive help system
- Command history and suggestions
- Batch command processing
- Configuration management
- Human-Device Interface (HDI) through Slack

### 3.5 AI Integration
- LangChain-based processing
- OpenAI API integration
- FAISS vector storage
- Semantic search capabilities
- Context-aware processing
- Natural language understanding
- Automated learning and adaptation
- Custom model fine-tuning
- Multi-model support
- Performance optimization

## 4. Technical Requirements

### 4.1 System Architecture
- Python-based backend
- FastAPI framework
- Modular service architecture
- API integration capabilities
- Secure data handling
- Scalable design
- Microservices architecture
- Event-driven processing
- Asynchronous operations
- Caching mechanisms
- Load balancing support

### 4.2 External Dependencies
- Google Cloud API
- FAISS (Vector Database)
- OpenAI API (LangChain)
- PDF processing libraries
- File system management
- Slack API
- OCR engines
- Cloud storage services
- Authentication services

### 4.3 Performance Requirements
- Document processing time < 30 seconds
- Task response time < 5 seconds
- 99.9% uptime
- Concurrent task handling
- Efficient resource utilization
- Scalable processing
- Memory optimization
- CPU utilization optimization
- Network bandwidth management
- Storage optimization

## 5. API Endpoints

### 5.1 Core Endpoints
- `/chat` - Main chat interface
- `/process-document` - Document processing
- `/process-document-enhanced` - Advanced document processing
- `/health` - System health check
- `/test-drive` - Google Drive connection test

### 5.2 Testing Endpoints
- `/test-ocr` - OCR functionality test
- `/test-folder` - Folder structure test
- `/test-document-flow` - Document processing flow test
- `/test-embeddings` - Vector embeddings test
- `/test-pdf` - PDF processing test
- `/test-similarity` - Document similarity test

### 5.3 Slack Integration
- `/slack/events` - Slack event handling
- `/slack/chat` - Slack chat interface

## 6. Security Requirements
- Secure API key management
- Data encryption
- Access control
- Audit logging
- Regular security updates
- Data backup and recovery
- Secure communication
- User authentication
- Role-based access control
- Compliance monitoring

## 7. Future Enhancements
- Web interface
- Mobile application
- Advanced analytics
- Custom workflow creation
- Integration with additional services
- Multi-language support
- Real-time collaboration
- Advanced AI capabilities
- Custom plugin system
- API marketplace
- **Hybrid Search Capabilities**: Implement keyword and hybrid search functionality to complement existing semantic search, combining vector similarity with traditional full-text search for improved accuracy and user experience
- **MCP (Model Context Protocol) Integration**: Implement standardized tool interface for AI assistants, enabling dynamic tool discovery and usage through protocols like those demonstrated in [LangConnect-Client](https://github.com/teddynote-lab/LangConnect-Client). This would restructure agent functions into MCP-compatible tools for enhanced AI assistant integration and workflow automation
- **Automatic Cloud Storage Cleanup Policies**: Implement automated cleanup policies for Google Cloud Storage buckets and Container Registry to prevent accumulation of build artifacts, Docker images, and deployment assets. Include configurable retention periods (e.g., 30 days for images, 7 days for failed builds), cost monitoring alerts, and automated garbage collection to optimize storage costs and maintain system efficiency. This enhancement addresses the ~$50/month potential savings identified during system optimization

## 8. Success Metrics
- User adoption rate
- Task completion efficiency
- Document processing accuracy
- System response time
- User satisfaction metrics
- Processing throughput
- Error rate reduction
- Resource utilization
- Cost efficiency
- System reliability

## 9. Development Phases

### Phase 1: MVP (Current)
- Basic document processing
- Simple folder organization
- Task management fundamentals
- Slack interface integration
- Core AI integration
- Basic security features
- Essential API integrations
- Initial testing framework
- FAISS vector storage
- Google Drive integration

### Phase 2: Enhancement
- Advanced document analysis
- Custom organization rules
- Enhanced task management
- Performance optimization
- Extended AI capabilities
- Advanced security features
- Additional API integrations
- Comprehensive testing
- Enhanced Slack integration
- Advanced vector search

### Phase 3: Expansion
- Web interface development
- Additional integrations
- Advanced analytics
- Mobile support
- Enterprise features
- Advanced AI capabilities
- Global deployment
- Enterprise security

## 10. Maintenance and Support
- Regular updates
- Bug fixes
- Performance monitoring
- User feedback integration
- Documentation updates
- Security patches
- Feature enhancements
- System optimization
- User support
- Training materials

## 11. Timeline and Milestones
- MVP completion: Q2 2024
- Phase 2 completion: Q3 2024
- Phase 3 completion: Q4 2024
- Ongoing maintenance and updates
- Regular feature releases
- Security updates
- Performance optimizations
- User feedback implementation

## 12. Proposed Tool-Based Agent Architecture (As Proposed)

### 12.1 Architecture Migration Plan
The system will migrate from service-based to tool-based agent architecture to enable better modularity, state management, and future LangGraph integration.

### 12.2 Agent Tool Groups

#### 12.2.1 File Management Agent (As Proposed)
- **Scope:** ALL file operations (scan, move, copy, delete, create files & folders)
- **Triggers:** Scheduled + On-demand from HDL Agent
- **State Management:** Maintains file inventory state
- **Intelligence:** Validates folder creation logic by searching/matching existing Entity DB table
- **Key Integration:** Queries DB Agent for entity matching before folder operations

#### 12.2.2 Extraction Agent (As Proposed)
- **Instructions:** Follow detailed extraction rules from document_processor.py
- **Email Handling:** 
  - Process email and attachments as separate documents
  - Generate clear email summary
  - Request HDL help for password-protected attachments
- **Confidence Scoring:** Generates confidence scores for all extractions
- **Human Review:** ALL extractions go to HDL Agent for review/approval/correction
- **Specialization:** Different extraction strategies by document type
- **Data Flow:** Pass results directly to Storage Agent

#### 12.2.3 Storage Agent (Vector) (As Proposed)
- **Input:** Receives chunked text + metadata from Extraction Agent
- **Embedding Generation:** Generates embeddings internally (optimal for vector DB)
- **Database Management:** Manages FAISS indices and optimal storage structure
- **Search Services:** Provides similarity search capabilities to other agents
- **Metadata:** Uses extraction fields defined in document_processor.py
- **Similarity Analysis:** On-demand trigger when other agents request it

#### 12.2.4 HDL Agent (Human-Device Interface) (As Proposed)
- **Workflow Management:** Complete human interaction workflow (request → review → approval → execute action)
- **Review Scope:** ALL task actions require human review
- **Learning:** Not implemented initially
- **Timeout Handling:** Retry after 12 hours if no human response
- **File Operations:** Can request File Management Agent for operations based on human decisions
- **Interface:** Slack-based interaction

#### 12.2.5 DB Agent (As Proposed)
- **Scope:** Basic CRUD operations for defined database tables
- **Entity Matching:** Provides entity matching services to File Management Agent
- **Tables Managed:** Entities, Tasks, Obligations, Authorizations, DocumentMetadata
- **Integration:** Simple structured data operations, no complex analytics
- **Purpose:** Support other agents with database operations

### 12.3 State Management System (As Proposed)
- **Centralized State:** AgentState class managing workflow state
- **State Manager:** Coordinates state across all agent tools
- **LangGraph Ready:** Architecture designed for easy LangGraph migration

### 12.4 Implementation Phases (As Proposed)

#### Phase 1: Tool Migration (As Proposed)
- Convert existing services to tool-based architecture
- Implement basic state management
- Establish agent coordination patterns

#### Phase 2: Enhanced Coordination (As Proposed)
- Implement advanced agent coordination
- Add error handling and retry mechanisms
- Optimize inter-agent communication

#### Phase 3: LangGraph Integration (As Proposed)
- Migrate to LangGraph for workflow orchestration
- Implement advanced state management
- Add workflow visualization and debugging

## File Discovery and Processing Flow

### File Discovery Service
The File Discovery Service is responsible for managing the initial processing of files found in the Google Drive Master folder. It acts as an intermediary between the folder scan and document processing.

#### Responsibilities:
1. **File Validation**
   - Validates file types (PDF, images, Google Docs, spreadsheets)
   - Ensures files are in a supported format
   - Rejects unsupported file types

2. **Processing State Management**
   - Checks if files have been previously processed
   - Maintains a First-In-First-Out (FIFO) processing queue
   - Tracks file processing status

3. **Queue Management**
   - Implements synchronous processing (one file at a time)
   - Maintains processing order based on discovery time
   - Handles file processing state transitions

### Document Processing History
A database table will be implemented to store document processing history, including:
- File ID and metadata
- Processing timestamp
- Processing status
- Entity information
- Processing results
- Error logs (if any)

### Processing Flow
1. Scheduler triggers folder scan
2. File Discovery Service:
   - Validates discovered files
   - Checks processing history
   - Adds new files to processing queue
3. Document Processor Service:
   - Processes files in FIFO order
   - One file at a time (synchronous)
   - Updates processing history
4. Entity Service handles organization
5. Notification Service sends updates

### 5.4 Human-Device Interface (HDI) Flow
1. **Review Request Process**
   - Agent sends review request to Slack
   - Message includes review instructions
   - Approval/Rejection options provided
   - Real-time status updates

2. **Confirmation Options**
   - :white_check_mark: Approve
   - :x: Reject
   - Custom response handling
   - Status tracking

3. **Response Handling**
   - Approval triggers next step
   - Rejection initiates review
   - Error handling
   - Status notifications

4. **Integration Points**
   - Slack message handling
   - Channel management
   - User interaction
   - Status tracking

### 5.5 Database Schema Requirements

#### 5.5.1 Core Tables

1. **Tasks Table**
   - Primary key: Task ID (Txxx)
   - Fields:
     - Description (Text)
     - Type (Enum: Payment, Reminder, etc.)
     - Entity (Foreign Key to Entities)
     - Due Date (Date)
     - Frequency (Text)
     - Status (Enum: Pending, Completed, etc.)
     - Priority (Enum: High, Medium, Low)
     - Notes (Text)

2. **Entities Table**
   - Primary key: Entity ID (Exxx)
   - Fields:
     - Name (Text)
     - Category (Enum: Education, Finance, etc.)
     - Contact Info (Text)
     - Notes (Text)

3. **Obligations Table**
   - Primary key: Obligation ID (Oxxx)
   - Fields:
     - Description (Text)
     - Related Entity (Foreign Key to Entities)
     - Frequency (Text)
     - Trigger Date (Date)
     - Reminder Lead Time (Integer, days)
     - Last Completed (Date)

4. **Authorizations Table**
   - Primary key: Auth ID (Axxx)
   - Fields:
     - Entity (Foreign Key to Entities)
     - Task Type (Enum: Payment, Access, etc.)
     - Level (Enum: Limited, Full, etc.)
     - Expiry (Date)
     - Notes (Text)

5. **Document Metadata Table (As Proposed)**
   - Primary key: Document ID (Google Drive file ID)
   - Fields:
     - Entity ID (Foreign Key to Entities)
     - File Name (Text)
     - Issue Date (Date)
     - Subject (Text)
     - Summary (Text)
     - Document Type (Text)
     - Drive Link (Text)
     - Processing Time (DateTime)
     - Confidence Scores (JSON)

#### 5.5.2 Relationships
- Tasks → Entities (Many-to-One)
- Obligations → Entities (Many-to-One)
- Authorizations → Entities (Many-to-One)
- Document Metadata → Entities (Many-to-One)
- Tasks → Obligations (Optional Many-to-One)

#### 5.5.3 Implementation Phases
1. **Phase 1: Core Structure**
   - Basic table creation
   - Primary relationships
   - Essential fields

2. **Phase 2: Extended Features**
   - Additional fields
   - Complex relationships
   - Indexing and optimization

3. **Phase 3: Advanced Features**
   - Audit logging
   - Version control
   - Advanced querying capabilities

#### 5.5.4 Data Integrity Rules
1. **Entity Management**
   - Unique Entity IDs
   - Required contact information
   - Category validation

2. **Task Management**
   - Valid due dates
   - Status transitions
   - Priority levels

3. **Obligation Tracking**
   - Valid frequency patterns
   - Trigger date validation
   - Completion tracking

4. **Authorization Control**
   - Expiry date validation
   - Level restrictions
   - Entity association validation