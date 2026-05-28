process BWA_MEM2_MEM {
    tag "${meta.id}"
    label 'process_high'
    container 'quay.io/biocontainers/bwa-mem2:2.2.1--hd03093a_5'

    input:
    tuple val(meta), path(reads)
    path  index_dir
    path  fasta

    output:
    tuple val(meta), path('*.bam'),     emit: bam
    tuple val(meta), path('*.bam.bai'), emit: bai
    path 'versions.yml',                emit: versions

    script:
    def prefix     = meta.id
    def rg         = "@RG\\tID:${prefix}\\tSM:${meta.sample}\\tPL:ILLUMINA\\tLB:${meta.sample}_lib1\\tPU:${prefix}"
    def read_list  = reads instanceof List ? reads.join(' ') : reads
    def index_base = "${index_dir}/${fasta.baseName}"
    """
    bwa-mem2 mem -t ${task.cpus} -R '${rg}' ${index_base} ${read_list} \\
        | samtools sort -@ ${task.cpus} -o ${prefix}.bam -
    samtools index ${prefix}.bam

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$(bwa-mem2 version 2>&1 | head -1)
        samtools: \$(samtools --version | head -1 | sed 's/samtools //')
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.bam ${prefix}.bam.bai
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: 2.2.1
        samtools: 1.19
    VERSIONS
    """
}
