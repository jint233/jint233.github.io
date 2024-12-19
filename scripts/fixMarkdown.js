const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

// 获取当前脚本所在目录的上一级路径
const folderPath = path.resolve(path.dirname(__dirname)); 
const batchSize = 10; // 每次处理的文件数量

function getMarkdownFiles(dir, files) {
  files = files || [];
  const filesAndDirs = fs.readdirSync(dir);
  for (const item of filesAndDirs) {
    const fullPath = path.join(dir, item);
    if (fs.statSync(fullPath).isDirectory()) {
      getMarkdownFiles(fullPath, files);
    } else if (fullPath.endsWith('.md')) {
      files.push(fullPath);
    }
  }
  return files;
}

const markdownFiles = getMarkdownFiles(folderPath);

function processBatch(files) {
  if (files.length === 0) return;

  const batch = files.splice(0, batchSize);
  const fileArgs = batch.map(file => `"${file}"`).join(' ');

  exec(`markdownlint --fix ${fileArgs}`, (err, stdout, stderr) => {
    if (err) {
      console.error(`Error fixing files: ${fileArgs}`);
      console.error(stderr);
      // 将错误写入日志文件
      fs.appendFileSync(path.join(__dirname, 'markdownlint-errors.log'), `Error fixing files: ${fileArgs}\n${stderr}\n`);
    } else {
      console.log(`Fixed files: ${batch.join(', ')}`);
    }
    processBatch(files);
  });
}

processBatch(markdownFiles.slice());