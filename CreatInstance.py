import main

if __name__ == '__main__':
    # @ 3:
    # 创建实例（抢鸡）
    params = main.read_params_from_file(main.file_path)  # 读取形参的值（你要抢的配置）
    main.creat_instance(**params)