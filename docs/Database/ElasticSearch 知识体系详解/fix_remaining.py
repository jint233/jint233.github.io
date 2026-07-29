import os

f7 = '/Users/admin/Notes/docs/Database/ElasticSearch 知识体系详解/第07讲.md'
with open(f7, 'r', encoding='utf-8') as f:
    c7 = f.read()

c7 = c7.replace('### 例子 (constant_score)\n\n首先创建数据\n\n```shell\nPOST /test-dsl-boosting/_bulk', '### 例子 (boosting query)\n\n首先创建数据\n\n```shell\nPOST /test-dsl-boosting/_bulk')
with open(f7, 'w', encoding='utf-8') as f:
    f.write(c7)


f8 = '/Users/admin/Notes/docs/Database/ElasticSearch 知识体系详解/第08讲.md'
with open(f8, 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

new_lines = []
for line in lines:
    if line.startswith('- **验证结果**') or line.startswith('- **match 多个词的本质**'):
        new_lines.append('')
        new_lines.append(line)
    elif line.startswith('用 term 查询计算每个文档相关度评分 _score'):
        # also need to wrap if it's considered part of the list item, but maybe putting it on a new line is enough
        new_lines.append(line)
    else:
        new_lines.append(line)

# Let's ensure no triple empty lines
final_lines = []
empty_count = 0
for l in new_lines:
    if l == '':
        empty_count += 1
        if empty_count <= 2:
            final_lines.append(l)
    else:
        empty_count = 0
        final_lines.append(l)

with open(f8, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

print("Fixed")
