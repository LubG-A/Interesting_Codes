# Wordle Solver

Wordle游戏自动求解器，基于n-gram统计和字典匹配算法。

## 编译

使用C++编译器（如g++）编译：
```sh
g++ solve.cpp -o wordle_solver
```

## 运行

确保以下文件在同一目录：
- `wordle_solver` (编译后的可执行文件)
- `english_quadgrams.txt` (n-gram统计数据)
- `word_list.txt` (字典文件)

直接运行可执行文件即可。

## 示例

![solve-wordle-STIFF](./res/solve-wordle-STIFF.png)
![solve-wordle-DRAMA](./res/solve-wordle-DRAMA.png)
