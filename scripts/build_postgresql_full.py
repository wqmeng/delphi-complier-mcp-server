#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速爬取 PostgreSQL 文档
使用预定义的完整 URL 列表
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.knowledge_base.scan_generic_documents import GenericDocumentScanner


# PostgreSQL 18 文档完整目录（从官方文档提取）
POSTGRESQL_DOCS = [
    # I. Tutorial
    "tutorial.html",
    "tutorial-start.html",
    "tutorial-createdb.html",
    "tutorial-accessdb.html",
    "tutorial-concepts.html",
    "tutorial-populate.html",
    "tutorial-select.html",
    "tutorial-join.html",
    "tutorial-agg.html",
    "tutorial-update.html",
    "tutorial-delete.html",
    
    # II. The SQL Language
    "sql.html",
    "sql-syntax.html",
    "sql-lexical-structure.html",
    "sql-keywords.html",
    "sql-identifiers.html",
    "sql-syntax-lexical.html",
    "sql-expressions.html",
    "sql-calls.html",
    "ddl.html",
    "ddl-basics.html",
    "ddl-default.html",
    "ddl-generated.html",
    "ddl-constraints.html",
    "ddl-system-columns.html",
    "ddl-modifying.html",
    "dml.html",
    "queries.html",
    "queries-overview.html",
    "queries-table-expressions.html",
    "queries-select-lists.html",
    "queries-union.html",
    "data-manipulation.html",
    "data-definition.html",
    
    # III. Advanced Features
    "advanced.html",
    "advanced-intro.html",
    "advanced-views.html",
    "advanced-check-constraints.html",
    "advanced-foreign-keys.html",
    "advanced-inheritance.html",
    
    # IV. Query Tuning
    "perform.html",
    "perform-intro.html",
    "perform-methods.html",
    "perform-statistics.html",
    
    # V. Data Definition
    "ddl.html",
    
    # VI. Data Types
    "datatype.html",
    "datatype-numeric.html",
    "datatype-money.html",
    "datatype-character.html",
    "datatype-binary.html",
    "datatype-datetime.html",
    "datatype-boolean.html",
    "datatype-enum.html",
    "datatype-geometric.html",
    "datatype-net-types.html",
    "datatype-bit-strings.html",
    "datatype-text-search.html",
    "datatype-uuid.html",
    "datatype-xml.html",
    "datatype-json.html",
    "datatype-array.html",
    "datatype-composite.html",
    "datatype-range-types.html",
    "datatype-domain.html",
    "datatype-oid.html",
    "datatype-pseudo.html",
    
    # VII. Functions and Operators
    "functions.html",
    "functions-logical.html",
    "functions-comparison.html",
    "functions-math.html",
    "functions-string.html",
    "functions-binarystring.html",
    "functions-bitstring.html",
    "functions-matching.html",
    "functions-datetime.html",
    "functions-enum.html",
    "functions-geometry.html",
    "functions-net.html",
    "functions-textsearch.html",
    "functions-xml.html",
    "functions-json.html",
    "functions-sequence.html",
    "functions-conditional.html",
    "functions-array.html",
    "functions-range.html",
    "functions-aggregate.html",
    "functions-window.html",
    "functions-srf.html",
    "functions-info.html",
    "functions-admin.html",
    "functions-trigger.html",
    
    # VIII. Type Conversion
    "typeconv.html",
    
    # IX. Indexes
    "indexes.html",
    "indexes-intro.html",
    "indexes-types.html",
    "indexes-multicolumn.html",
    "indexes-unique.html",
    "indexes-express.html",
    "indexes-partial.html",
    
    # X. Full Text Search
    "textsearch.html",
    "textsearch-intro.html",
    "textsearch-tables.html",
    "textsearch-controls.html",
    "textsearch-parsers.html",
    "textsearch-dictionaries.html",
    "textsearch-configuration.html",
    
    # XI. Concurrency Control
    "mvcc.html",
    "mvcc-intro.html",
    "mvcc-transactions.html",
    
    # XII. Performance Tips
    "performance-tips.html",
    
    # XIII. Parallel Query
    "parallel-query.html",
    
    # XIV. Server Configuration
    "runtime-config.html",
    "runtime-config-preset.html",
    "runtime-config-connection.html",
    "runtime-config-security.html",
    "runtime-config-resource.html",
    "runtime-config-wal.html",
    "runtime-config-query.html",
    "runtime-config-logging.html",
    "runtime-config-process-title.html",
    "runtime-config-statistics.html",
    "runtime-config-autovacuum.html",
    "runtime-config-client.html",
    "runtime-config-compatible.html",
    "runtime-config-custom.html",
    "runtime-config-developer.html",
    
    # XV. Client Authentication
    "client-authentication.html",
    
    # XVI. User Management
    "user-manag.html",
    
    # XVII. Database Maintenance
    "maintenance.html",
    "routine-vacuuming.html",
    "routine-reindex.html",
    
    # XVIII. Backup and Restore
    "backup.html",
    "backup-dump.html",
    "backup-file.html",
    "continuous-archiving.html",
    
    # XIX. High Availability
    "high-availability.html",
    
    # XX. Recovery Configuration
    "recovery-config.html",
    
    # XXI. Monitoring
    "monitoring.html",
    "monitoring-stats.html",
    "monitoring-locks.html",
    "monitoring-progress.html",
    
    # XXII. Disk Usage
    "diskusage.html",
    
    # XXIII. WAL
    "wal.html",
    
    # XXIV. Logical Replication
    "logical-replication.html",
    
    # XXV. Just-in-Time Compilation
    "jit.html",
    
    # SQL Commands
    "sql-commands.html",
    "sql-abort.html",
    "sql-alteraggregate.html",
    "sql-altercollation.html",
    "sql-alterconversion.html",
    "sql-alterdatabase.html",
    "sql-alterdefaultprivileges.html",
    "sql-alterdomain.html",
    "sql-altereventtrigger.html",
    "sql-alterextension.html",
    "sql-alterforeigndatawrapper.html",
    "sql-alterforeigntable.html",
    "sql-alterfunction.html",
    "sql-altergroup.html",
    "sql-alterindex.html",
    "sql-alterlanguage.html",
    "sql-alterlargeobject.html",
    "sql-altermaterializedview.html",
    "sql-alteropclass.html",
    "sql-alteroperator.html",
    "sql-alteropfamily.html",
    "sql-alterpolicy.html",
    "sql-alterprocedure.html",
    "sql-alterpublication.html",
    "sql-alterrole.html",
    "sql-alterroutine.html",
    "sql-alterrule.html",
    "sql-alterschema.html",
    "sql-altersequence.html",
    "sql-alterserver.html",
    "sql-alterstatistics.html",
    "sql-altersubscription.html",
    "sql-altersystem.html",
    "sql-altertable.html",
    "sql-altertablespace.html",
    "sql-altertextsearchconfiguration.html",
    "sql-altertextsearchdictionary.html",
    "sql-altertextsearchparser.html",
    "sql-altertextsearchtemplate.html",
    "sql-altertrigger.html",
    "sql-altertype.html",
    "sql-alteruser.html",
    "sql-alterusermapping.html",
    "sql-alterview.html",
    "sql-analyze.html",
    "sql-begin.html",
    "sql-call.html",
    "sql-checkpoint.html",
    "sql-close.html",
    "sql-cluster.html",
    "sql-comment.html",
    "sql-commit.html",
    "sql-commitprepared.html",
    "sql-copy.html",
    "sql-createaccessmethod.html",
    "sql-createaggregate.html",
    "sql-createcast.html",
    "sql-createcollation.html",
    "sql-createconversion.html",
    "sql-createdatabase.html",
    "sql-createdomain.html",
    "sql-createeventtrigger.html",
    "sql-createextension.html",
    "sql-createforeigndatawrapper.html",
    "sql-createforeigntable.html",
    "sql-createfunction.html",
    "sql-creategroup.html",
    "sql-createindex.html",
    "sql-createlanguage.html",
    "sql-createlargeobject.html",
    "sql-creatematerializedview.html",
    "sql-createopclass.html",
    "sql-createoperator.html",
    "sql-createopfamily.html",
    "sql-createpolicy.html",
    "sql-createprocedure.html",
    "sql-createpublication.html",
    "sql-createrole.html",
    "sql-createrule.html",
    "sql-createschema.html",
    "sql-createsequence.html",
    "sql-createserver.html",
    "sql-createstatistics.html",
    "sql-createsubscription.html",
    "sql-createtable.html",
    "sql-createtableas.html",
    "sql-createtablespace.html",
    "sql-createtextsearchconfiguration.html",
    "sql-createtextsearchdictionary.html",
    "sql-createtextsearchparser.html",
    "sql-createtextsearchtemplate.html",
    "sql-createtransform.html",
    "sql-createtrigger.html",
    "sql-createtsconfig.html",
    "sql-createtsdict.html",
    "sql-createtsparser.html",
    "sql-createtstemplate.html",
    "sql-createtype.html",
    "sql-createuser.html",
    "sql-createusermapping.html",
    "sql-createview.html",
    "sql-deallocate.html",
    "sql-declare.html",
    "sql-delete.html",
    "sql-discard.html",
    "sql-distinct.html",
    "sql-do.html",
    "sql-dropaccessmethod.html",
    "sql-dropaggregate.html",
    "sql-dropcast.html",
    "sql-dropcollation.html",
    "sql-dropconversion.html",
    "sql-dropdatabase.html",
    "sql-dropdomain.html",
    "sql-dropeventtrigger.html",
    "sql-dropextension.html",
    "sql-dropforeigndatawrapper.html",
    "sql-dropforeigntable.html",
    "sql-dropfunction.html",
    "sql-dropgroup.html",
    "sql-dropindex.html",
    "sql-droplanguage.html",
    "sql-droplargeobject.html",
    "sql-dropmaterializedview.html",
    "sql-dropopclass.html",
    "sql-dropoperator.html",
    "sql-dropopfamily.html",
    "sql-droppolicy.html",
    "sql-dropprocedure.html",
    "sql-droppublication.html",
    "sql-droprole.html",
    "sql-droprule.html",
    "sql-dropschema.html",
    "sql-dropsequence.html",
    "sql-dropserver.html",
    "sql-dropstatistics.html",
    "sql-dropsubscription.html",
    "sql-droptable.html",
    "sql-droptablespace.html",
    "sql-droptextsearchconfiguration.html",
    "sql-droptextsearchdictionary.html",
    "sql-droptextsearchparser.html",
    "sql-droptextsearchtemplate.html",
    "sql-droptransform.html",
    "sql-droptrigger.html",
    "sql-droptsconfig.html",
    "sql-droptsdict.html",
    "sql-droptsparser.html",
    "sql-droptstemplate.html",
    "sql-droptype.html",
    "sql-dropuser.html",
    "sql-dropusermapping.html",
    "sql-dropview.html",
    "sql-end.html",
    "sql-execute.html",
    "sql-explain.html",
    "sql-fetch.html",
    "sql-grant.html",
    "sql-importforeignschema.html",
    "sql-insert.html",
    "sql-listen.html",
    "sql-load.html",
    "sql-lock.html",
    "sql-move.html",
    "sql-notify.html",
    "sql-prepare.html",
    "sql-preparetransaction.html",
    "sql-reassign-owned.html",
    "sql-refreshmaterializedview.html",
    "sql-reindex.html",
    "sql-release-savepoint.html",
    "sql-reset.html",
    "sql-revoke.html",
    "sql-rollback.html",
    "sql-rollbackprepared.html",
    "sql-rollbackto.html",
    "sql-savepoint.html",
    "sql-security-label.html",
    "sql-select.html",
    "sql-selectinto.html",
    "sql-set.html",
    "sql-setconstraints.html",
    "sql-setrole.html",
    "sql-set-session-authorization.html",
    "sql-settransaction.html",
    "sql-show.html",
    "sql-starttransaction.html",
    "sql-truncate.html",
    "sql-unlisten.html",
    "sql-update.html",
    "sql-vacuum.html",
    "sql-values.html",
    "sql-with.html",
]


def build_postgresql_kb_full():
    """构建 PostgreSQL 完整文档知识库"""
    print("=" * 60)
    print("构建 PostgreSQL 完整文档知识库")
    print("=" * 60)
    
    server_root = Path(__file__).parent.parent.parent
    kb_dir = str(server_root / "data" / "document-knowledge-base")
    Path(kb_dir).mkdir(parents=True, exist_ok=True)
    
    scanner = GenericDocumentScanner(kb_dir)
    
    base_url = "https://www.postgresql.org/docs/current/"
    urls = [base_url + doc for doc in POSTGRESQL_DOCS]
    
    print(f"\n总共 {len(urls)} 个文档页面")
    
    start_time = time.time()
    success = 0
    failed = 0
    total_size = 0
    
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url.split('/')[-1][:50]}...")
        
        result = scanner.add_web_document(url)
        
        if result and not (isinstance(result, dict) and 'error' in result):
            success += 1
            total_size += result.get('size', 0)
        else:
            failed += 1
    
    elapsed = time.time() - start_time
    
    print(f"\n" + "=" * 60)
    print("完成")
    print("=" * 60)
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    print(f"耗时: {elapsed:.1f} 秒")
    if success > 0:
        print(f"平均: {elapsed/success:.2f} 秒/页面")
    
    stats = scanner.get_statistics()
    print(f"\n知识库总文档数: {stats['total_documents']}")


if __name__ == "__main__":
    build_postgresql_kb_full()
