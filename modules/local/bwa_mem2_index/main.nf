process BWA_MEM2_INDEX {
    tag "${fasta.baseName}"
    label 'process_high'
    container 'quay.io/biocontainers/bwa-mem2:2.2.1--hd03093a_5'

    input:
    path fasta

    output:
    path 'bwa_mem2_index/', emit: index
    path 'versions.yml',    emit: versions

    script:
    """
    mkdir -p bwa_mem2_index
    bwa-mem2 index -p bwa_mem2_index/${fasta.baseName} ${fasta}

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$(bwa-mem2 version 2>&1 | head -1)
    VERSIONS
    """

    stub:
    """
    mkdir -p bwa_mem2_index
    touch bwa_mem2_index/${fasta.baseName}.amb
    touch bwa_mem2_index/${fasta.baseName}.ann
    touch bwa_mem2_index/${fasta.baseName}.bwt.2bit.64
    touch bwa_mem2_index/${fasta.baseName}.pac
    touch bwa_mem2_index/${fasta.baseName}.0123
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: 2.2.1
    VERSIONS
    """
}
