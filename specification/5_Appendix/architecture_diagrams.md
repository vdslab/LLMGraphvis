# LLMGraphvis アーキテクチャ図

## 全体構造図

```mermaid
graph TB
    subgraph "LLMGraphvis"
        API[API Service]
        NMCP[NetworkXMCP Service]
        Common[Common Modules]
        
        API --> Common
        NMCP --> Common
        API <--> NMCP
    end
    
    subgraph "External"
        DB[(Database)]
        Client[Client Application]
    end
    
    API --> DB
    NMCP --> DB
    Client <--> API
```

## 共通モジュール構造

```mermaid
graph TB
    subgraph "common/"
        subgraph "models/"
            CM_Base[base.py]
            CM_Network[network.py]
            CM_Graph[graph.py]
            CM_Response[response.py]
        end
        
        subgraph "utils/"
            subgraph "graphml/"
                CU_Parser[parser.py]
                CU_Converter[converter.py]
                CU_Validator[validator.py]
                CU_Fixer[fixer.py]
            end
        end
        
        subgraph "exceptions/"
            CE_Base[base.py]
            CE_Validation[validation.py]
            CE_Processing[processing.py]
            CE_Communication[communication.py]
        end
        
        subgraph "logging/"
            CL_Config[config.py]
            CL_Formatters[formatters.py]
        end
    end
```

## API サービス構造

```mermaid
graph TB
    subgraph "API/"
        subgraph "core/"
            AC_Config[config.py]
            AC_Errors[errors.py]
            AC_Security[security.py]
        end
        
        subgraph "models/"
            AM_User[user.py]
            AM_Conversation[conversation.py]
            AM_Network[network.py]
            AM_Chat[chat.py]
        end
        
        subgraph "schemas/"
            AS_User[user.py]
            AS_Conversation[conversation.py]
            AS_Network[network.py]
            AS_Chat[chat.py]
        end
        
        subgraph "routers/"
            AR_Auth[auth.py]
            AR_Chat[chat.py]
            
            subgraph "network/"
                ARN_Init[__init__.py]
                ARN_Upload[upload.py]
                ARN_Export[export.py]
                ARN_Visualization[visualization.py]
                ARN_Layout[layout.py]
            end
        end
        
        subgraph "services/"
            subgraph "graphml/"
                ASG_Validator[validator.py]
                ASG_Converter[converter.py]
                ASG_Parser[parser.py]
            end
            
            subgraph "visualization/"
                ASV_Cytoscape[cytoscape.py]
                ASV_Visdata[visdata.py]
                ASV_Custom[custom.py]
            end
            
            subgraph "layout/"
                ASL_Manager[manager.py]
                ASL_Validator[validator.py]
                ASL_Processor[processor.py]
            end
            
            AS_MCP[mcp_client.py]
            AS_LLM[llm.py]
            AS_Knowledge[knowledge.py]
        end
        
        A_Main[main.py]
        A_Database[database.py]
        A_Auth[auth.py]
    end
```

## NetworkXMCP サービス構造

```mermaid
graph TB
    subgraph "NetworkXMCP/"
        subgraph "core/"
            NC_Config[config.py]
            NC_Errors[errors.py]
        end
        
        subgraph "database/"
            ND_Init[__init__.py]
            ND_Models[models.py]
            ND_Session[session.py]
            ND_Operations[operations.py]
        end
        
        subgraph "models/"
            NM_Init[__init__.py]
            NM_Database[database.py]
            NM_API[api.py]
            NM_Graph[graph.py]
        end
        
        subgraph "tools/"
            NT_Init[__init__.py]
            NT_Creation[creation.py]
            NT_Parsing[parsing.py]
            NT_Export[export.py]
            NT_Analysis[analysis.py]
        end
        
        subgraph "graphml/"
            NG_Init[__init__.py]
            NG_Converter[converter.py]
            NG_Validator[validator.py]
            NG_Fixer[fixer.py]
        end
        
        subgraph "layouts/"
            NL_Init[__init__.py]
            NL_Functions[layout_functions.py]
        end
        
        subgraph "metrics/"
            NM_Init[__init__.py]
            NM_Centrality[centrality_functions.py]
        end
        
        subgraph "cache/"
            NC_Init[__init__.py]
            NC_Manager[manager.py]
            NC_Strategies[strategies.py]
            NC_Invalidation[invalidation.py]
        end
        
        N_Main[main.py]
    end
```

## データフロー図

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Common
    participant NetworkXMCP
    participant Database
    
    Client->>API: ネットワークアップロード
    API->>Common: GraphML検証
    Common-->>API: 検証結果
    API->>NetworkXMCP: GraphML変換リクエスト
    NetworkXMCP->>Common: GraphML処理ユーティリティ使用
    Common-->>NetworkXMCP: 処理結果
    NetworkXMCP-->>API: 変換結果
    API->>Database: ネットワーク保存
    Database-->>API: 保存結果
    API-->>Client: アップロード結果
    
    Client->>API: レイアウト変更リクエスト
    API->>NetworkXMCP: レイアウト計算リクエスト
    NetworkXMCP->>Database: キャッシュ確認
    Database-->>NetworkXMCP: キャッシュ結果
    
    alt キャッシュヒット
        NetworkXMCP-->>API: キャッシュからレイアウト結果
    else キャッシュミス
        NetworkXMCP->>NetworkXMCP: レイアウト計算
        NetworkXMCP->>Database: レイアウト結果キャッシュ
        NetworkXMCP-->>API: レイアウト結果
    end
    
    API-->>Client: レイアウト結果
```

## 依存関係図

```mermaid
graph TD
    subgraph "依存関係"
        Client[Client Application]
        API[API Service]
        NMCP[NetworkXMCP Service]
        Common[Common Modules]
        DB[(Database)]
        
        Client --> API
        API --> Common
        API --> NMCP
        API --> DB
        NMCP --> Common
        NMCP --> DB
    end
```

## リファクタリング前後の比較

```mermaid
graph TB
    subgraph "リファクタリング前"
        API_Before[API Service<br>- 大きなファイル<br>- 責務混在<br>- 重複コード]
        NMCP_Before[NetworkXMCP Service<br>- 大きなファイル<br>- 責務混在<br>- 重複コード]
        
        API_Before <--> NMCP_Before
    end
    
    subgraph "リファクタリング後"
        API_After[API Service<br>- モジュール分割<br>- 責務明確化<br>- コード再利用]
        NMCP_After[NetworkXMCP Service<br>- モジュール分割<br>- 責務明確化<br>- コード再利用]
        Common_After[Common Modules<br>- 共通機能<br>- 標準化<br>- 再利用性]
        
        API_After --> Common_After
        NMCP_After --> Common_After
        API_After <--> NMCP_After
    end